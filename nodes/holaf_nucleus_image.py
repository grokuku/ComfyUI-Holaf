# Copyright (C) 2026 Holaf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Nucleus-Image (Holaf) — A "black box" ComfyUI node for NucleusAI/Nucleus-Image.

Nucleus-Image is a 17B sparse MoE diffusion transformer (~2B active per pass).
This node uses the HuggingFace ``diffusers`` pipeline under the hood.

Features
--------
- Auto-downloads the model on first use (~80 GB)
- Stores model files locally in its own folder (easy to cleanup)
- Negative prompt support
- Text KV caching for faster inference
- LRU-aware VRAM management (keeps layers on GPU while VRAM permits,
  evicts least-recently-used layers when VRAM exceeds threshold)
- ComfyUI progress bar integration

Requirements
------------
    pip install git+https://github.com/huggingface/diffusers
    pip install transformers>=4.57 accelerate huggingface_hub sentencepiece

The ``NucleusMoEImagePipeline`` class is only available in diffusers >= 0.38
(main branch as of April 2026).  The stable 0.37 release does NOT include it.
"""

import os
import gc
import logging
from collections import OrderedDict

import numpy as np
import torch

logger = logging.getLogger("Holaf.NucleusImage")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_REPO_ID = "NucleusAI/Nucleus-Image"

# All model files are stored next to this script for easy cleanup.
# To fully remove the model, simply delete the ``nucleus_image_model/`` folder.
NODE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(NODE_DIR, "nucleus_image_model")

# Module-level pipeline cache — survives across node invocations within the
# same process so the model is only loaded once.
_cached_pipeline = None
_cached_offload_mode = None
_cached_kv_cache = None
_cached_vram_threshold = None


# ---------------------------------------------------------------------------
# Smart LRU Layer Offloader
# ---------------------------------------------------------------------------

class LayerLRUOffloader:
    """
    Manages GPU memory for transformer blocks using an LRU strategy.

    Instead of moving every block back to CPU after each forward pass
    (slow, like ``enable_sequential_cpu_offload``), this manager keeps
    blocks on GPU while VRAM is below a configurable threshold. When
    VRAM exceeds the threshold, the least-recently-used block is evicted
    to CPU, freeing space for the next block that needs to execute.

    This provides a sweet spot between speed and VRAM usage:
    - Frequently used blocks stay on GPU (fast)
    - Rarely used blocks are offloaded (saves VRAM)
    - Only actual usage triggers GPU↔CPU transfers
    """

    def __init__(self, vram_threshold: float = 0.75):
        self.vram_threshold = vram_threshold
        self.lru: OrderedDict = OrderedDict()  # block index -> block module
        self.on_gpu: dict = {}                  # block index -> bool
        self._hooks_installed = False

    # ------------------------------------------------------------------
    # VRAM monitoring
    # ------------------------------------------------------------------

    def vram_fraction(self) -> float:
        """Return current VRAM usage as a fraction of total GPU memory."""
        if not torch.cuda.is_available():
            return 1.0
        total = torch.cuda.get_device_properties(0).total_memory
        reserved = torch.cuda.memory_reserved(0)
        return reserved / total

    # ------------------------------------------------------------------
    # LRU operations
    # ------------------------------------------------------------------

    def touch(self, idx: int, block: torch.nn.Module) -> None:
        """Mark a block as recently used and ensure it is on GPU."""
        if self.on_gpu.get(idx, False):
            # Already on GPU — just update LRU order
            self.lru.move_to_end(idx)
            return

        # Move block to GPU
        block.to("cuda")
        self.on_gpu[idx] = True
        self.lru[idx] = block

        # Evict if VRAM is getting tight
        self._evict_if_needed(exclude=idx)

    def _evict_if_needed(self, exclude: int = None) -> None:
        """Evict LRU blocks to CPU until VRAM is below threshold."""
        gc.collect()
        torch.cuda.empty_cache()

        while self.vram_fraction() > self.vram_threshold:
            evicted = False
            for idx in list(self.lru.keys()):
                if idx != exclude and self.on_gpu.get(idx, False):
                    block = self.lru[idx]
                    block.to("cpu")
                    self.on_gpu[idx] = False
                    del self.lru[idx]
                    gc.collect()
                    torch.cuda.empty_cache()
                    evicted = True
                    logger.debug(
                        "[Nucleus-Image LRU] Evicted block %d to CPU (VRAM: %.1f%%)",
                        idx, self.vram_fraction() * 100,
                    )
                    break
            if not evicted:
                break

    def offload_all(self) -> None:
        """Move all tracked blocks back to CPU and clear state."""
        for idx, block in list(self.lru.items()):
            if self.on_gpu.get(idx, False):
                block.to("cpu")
                self.on_gpu[idx] = False
        self.lru.clear()
        gc.collect()
        torch.cuda.empty_cache()

    # ------------------------------------------------------------------
    # Hook management
    # ------------------------------------------------------------------

    def install_hooks(self, transformer: torch.nn.Module) -> bool:
        """
        Install pre/post forward hooks on each transformer block
        to manage GPU memory transparently during the denoising loop.

        Returns True if hooks were installed on individual blocks,
        False if the transformer blocks could not be discovered.
        """
        blocks = self._discover_blocks(transformer)
        if not blocks:
            logger.warning(
                "[Nucleus-Image LRU] Could not discover transformer blocks. "
                "Falling back to whole-transformer offloading."
            )
            return False

        self.lru.clear()
        self.on_gpu.clear()

        for i, block in enumerate(blocks):
            # Store references on the block for the hook closures
            block._lru_idx = i
            block._lru_offloader = self

            # Pre-forward: move block to GPU before it executes
            block.register_forward_pre_hook(self._pre_forward_hook, with_kwargs=True)
            # Post-forward: check VRAM after block executed, evict if needed
            block.register_forward_hook(self._post_forward_hook)

        self._hooks_installed = True
        logger.info(
            "[Nucleus-Image LRU] Installed hooks on %d transformer blocks.",
            len(blocks),
        )
        return True

    def uninstall_hooks(self, transformer: torch.nn.Module) -> None:
        """Remove LRU hooks and clean up block attributes."""
        blocks = self._discover_blocks(transformer)
        for block in blocks:
            if hasattr(block, '_lru_idx'):
                del block._lru_idx
            if hasattr(block, '_lru_offloader'):
                del block._lru_offloader
        # Note: PyTorch doesn't support removing specific hooks easily,
        # but the hooks will be no-ops if _lru_offloader is deleted.
        self._hooks_installed = False

    @staticmethod
    def _pre_forward_hook(module, args, kwargs):
        """Move the block to GPU before its forward pass."""
        offloader = getattr(module, '_lru_offloader', None)
        if offloader is not None:
            idx = module._lru_idx
            offloader.touch(idx, module)
        return args, kwargs

    @staticmethod
    def _post_forward_hook(module, input, output):
        """After forward, evict LRU blocks if VRAM exceeds threshold."""
        offloader = getattr(module, '_lru_offloader', None)
        if offloader is not None:
            offloader._evict_if_needed(exclude=module._lru_idx)
        return output

    @staticmethod
    def _discover_blocks(transformer: torch.nn.Module) -> list:
        """
        Discover the list of sequential transformer blocks.

        NucleusMoEImageTransformer2DModel stores them as
        ``self.transformer_blocks`` (nn.ModuleList).
        Falls back to other common names.
        """
        for attr_name in (
            "transformer_blocks",   # Nucleus-Image, FLUX, SD3
            "blocks",              # Some architectures
            "layers",              # Common alternative
        ):
            blocks = getattr(transformer, attr_name, None)
            if blocks is not None and isinstance(blocks, torch.nn.ModuleList) and len(blocks) > 1:
                return list(blocks)

        # Last resort: look for a ModuleList among direct children
        for name, child in transformer.named_children():
            if isinstance(child, torch.nn.ModuleList) and len(child) > 1:
                return list(child)

        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_diffusers():
    """Verify that the required diffusers version is installed."""
    try:
        from diffusers import NucleusMoEImagePipeline  # noqa: F401
        return True
    except ImportError:
        return False


def _ensure_model(model_dir: str, repo_id: str):
    """Download the model from HuggingFace Hub if not already present locally."""
    sentinel = os.path.join(model_dir, "model_index.json")
    if os.path.isfile(sentinel):
        logger.info("[Nucleus-Image] Model found at %s", model_dir)
        return

    logger.info("[Nucleus-Image] Model not found locally — downloading from %s", repo_id)
    logger.info("[Nucleus-Image] Total size is ~80 GB. This will take a while. Please wait.")
    os.makedirs(model_dir, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
        snapshot_download(
            repo_id=repo_id,
            local_dir=model_dir,
            repo_type="model",
        )
        logger.info("[Nucleus-Image] Download complete.")
    except ImportError:
        raise ImportError(
            "huggingface_hub is required for automatic model download.\n"
            "Install it with:  pip install huggingface_hub"
        )


def _load_pipeline(model_dir: str, offload_mode: str, enable_kv_cache: bool,
                   vram_threshold: float):
    """
    Load (or return cached) DiffusionPipeline with the chosen offload strategy.

    Supported offload modes:
    - ``lru_offload``  : Smart LRU management at transformer-block level.
                         Blocks stay on GPU while VRAM < threshold, evicted
                         LRU when VRAM exceeds it.  Best balance of speed/VRAM.
    - ``sequential_offload`` : Block-by-block, always offloaded after use.
                               Minimal VRAM but slow.
    - ``full_gpu``     : Everything on GPU.  Requires ~52 GB VRAM.
    """
    global _cached_pipeline, _cached_offload_mode, _cached_kv_cache, _cached_vram_threshold

    # Reuse cached pipeline when settings are identical
    if _cached_pipeline is not None:
        if (_cached_offload_mode == offload_mode
                and _cached_kv_cache == enable_kv_cache
                and _cached_vram_threshold == vram_threshold):
            logger.info("[Nucleus-Image] Reusing cached pipeline.")
            return _cached_pipeline
        # Settings changed — free the old pipeline
        logger.info(
            "[Nucleus-Image] Settings changed. Reloading pipeline.",
        )
        # Remove LRU hooks if they were installed
        if hasattr(_cached_pipeline, '_lru_offloader') and _cached_pipeline._lru_offloader is not None:
            _cached_pipeline._lru_offloader.offload_all()
            _cached_pipeline._lru_offloader.uninstall_hooks(_cached_pipeline.transformer)
        del _cached_pipeline
        _cached_pipeline = None
        gc.collect()
        torch.cuda.empty_cache()

    # ------------------------------------------------------------------
    # Import the pipeline class
    # ------------------------------------------------------------------
    try:
        from diffusers import DiffusionPipeline
    except ImportError:
        raise ImportError(
            "The 'diffusers' library is required but not installed.\n"
            "The NucleusMoEImagePipeline is only available in diffusers >= 0.38.\n"
            "Install the latest version with:\n"
            "  pip install git+https://github.com/huggingface/diffusers"
        )

    # --- Load pipeline weights ---
    logger.info("[Nucleus-Image] Loading pipeline from %s (bfloat16) ...", model_dir)
    pipe = DiffusionPipeline.from_pretrained(
        model_dir,
        torch_dtype=torch.bfloat16,
    )

    # --- Apply VRAM offloading strategy ---
    lru_offloader = None

    if offload_mode == "lru_offload":
        # --- LRU-aware block-level offloading ---
        # Strategy:
        #   1. Move all components to CPU first.
        #   2. Move the transformer's "shell" (non-block params: embeddings,
        #      norms, proj_out) to GPU permanently — these are small (~1-2 GB).
        #   3. Keep transformer blocks on CPU; install forward hooks that
        #      move each block to GPU on-demand and evict LRU when VRAM > threshold.
        #   4. Text encoder and VAE are loaded to GPU on-demand for their
        #      respective phases, then immediately offloaded.
        lru_offloader = LayerLRUOffloader(vram_threshold=vram_threshold)

        # Move everything to CPU first
        pipe.to("cpu")
        gc.collect()
        torch.cuda.empty_cache()

        # Discover blocks
        blocks = LayerLRUOffloader._discover_blocks(pipe.transformer)

        if blocks:
            # Move entire transformer to GPU (so non-block params are there),
            # then move only the blocks back to CPU.
            pipe.transformer.to("cuda")
            for block in blocks:
                block.to("cpu")
            logger.info(
                "[Nucleus-Image LRU] Transformer shell on GPU, %d blocks on CPU.",
                len(blocks),
            )
        else:
            # Fallback: keep entire transformer on CPU, hooks will
            # move it as a whole before each forward.
            pipe.transformer.to("cpu")
            logger.warning(
                "[Nucleus-Image LRU] Could not split transformer shell/blocks. "
                "Using whole-transformer offloading (slower)."
            )

        # Install the LRU hooks on transformer blocks
        lru_offloader.install_hooks(pipe.transformer)

        # Store the offloader on the pipeline for cleanup
        pipe._lru_offloader = lru_offloader

        logger.info(
            "[Nucleus-Image] VRAM mode: LRU offload (threshold %.0f%%, %d blocks).",
            vram_threshold * 100, len(blocks),
        )

        # Only offload text_encoder and VAE sequentially.
        # The transformer is managed exclusively by LayerLRUOffloader hooks.
        # Including "transformer" in the offload sequence would conflict with
        # our LRU block-level hooks, causing double-management of GPU memory.
        pipe.model_cpu_offload_seq = "text_encoder->vae"
        pipe.enable_sequential_cpu_offload()

    elif offload_mode == "sequential_offload":
        # Block-by-block, always moved back to CPU after each forward.
        # Peak VRAM ≈ 2–4 GB, but significantly slower.
        pipe.enable_sequential_cpu_offload()
        logger.info("[Nucleus-Image] VRAM mode: sequential offload (minimal VRAM, slow).")

    else:  # full_gpu
        # Everything on GPU.  Requires ~52 GB VRAM.
        pipe.to("cuda")
        logger.info("[Nucleus-Image] VRAM mode: full GPU (requires ~52 GB VRAM).")

    # --- Text KV caching ---
    if enable_kv_cache:
        try:
            from diffusers import TextKVCacheConfig
            pipe.transformer.enable_cache(TextKVCacheConfig())
            logger.info("[Nucleus-Image] Text KV cache enabled.")
        except (ImportError, AttributeError):
            logger.warning(
                "[Nucleus-Image] TextKVCacheConfig not available in your "
                "diffusers version. Skipping KV cache. Update diffusers for "
                "better performance."
            )

    # Cache for future calls
    _cached_pipeline = pipe
    _cached_offload_mode = offload_mode
    _cached_kv_cache = enable_kv_cache
    _cached_vram_threshold = vram_threshold

    return pipe


def _unload_pipeline():
    """Fully unload the cached pipeline and free GPU memory."""
    global _cached_pipeline, _cached_offload_mode, _cached_kv_cache, _cached_vram_threshold
    if _cached_pipeline is not None:
        # Clean up LRU offloader if present
        if hasattr(_cached_pipeline, '_lru_offloader') and _cached_pipeline._lru_offloader is not None:
            _cached_pipeline._lru_offloader.offload_all()
            _cached_pipeline._lru_offloader.uninstall_hooks(_cached_pipeline.transformer)
        del _cached_pipeline
        _cached_pipeline = None
        _cached_offload_mode = None
        _cached_kv_cache = None
        _cached_vram_threshold = None
        gc.collect()
        torch.cuda.empty_cache()
        logger.info("[Nucleus-Image] Pipeline unloaded and GPU cache cleared.")


# ---------------------------------------------------------------------------
# ComfyUI Node
# ---------------------------------------------------------------------------

class HolafNucleusImage:
    """
    Generate images with NucleusAI/Nucleus-Image.

    A 17B sparse MoE diffusion transformer (~2B active per forward pass).
    This is a standalone "black box" node — it auto-downloads the model on
    first use and stores all files in its own directory for easy cleanup.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "width": (
                    "INT",
                    {"default": 1024, "min": 256, "max": 2048, "step": 16},
                ),
                "height": (
                    "INT",
                    {"default": 1024, "min": 256, "max": 2048, "step": 16},
                ),
                "steps": (
                    "INT",
                    {"default": 50, "min": 1, "max": 200, "step": 1},
                ),
                "guidance_scale": (
                    "FLOAT",
                    {"default": 4.0, "min": 1.0, "max": 20.0, "step": 0.5},
                ),
                "seed": (
                    "INT",
                    {"default": 0, "min": 0, "max": 0xffffffffffffffff},
                ),
                "offload_mode": (
                    ["lru_offload", "sequential_offload", "full_gpu"],
                    {"default": "lru_offload"},
                ),
                "vram_threshold": (
                    "FLOAT",
                    {"default": 0.83, "min": 0.3, "max": 0.95, "step": 0.05,
                     "tooltip": "VRAM limit for LRU offload. 0.83 ≈ 10 GB on a 12 GB GPU."},
                ),
                "enable_kv_cache": ("BOOLEAN", {"default": True}),
                "clean_vram_before": ("BOOLEAN", {"default": True}),
                "unload_after_generate": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("IMAGE", "INFO")
    FUNCTION = "generate"
    CATEGORY = "Holaf"

    def generate(
        self,
        prompt,
        negative_prompt,
        width,
        height,
        steps,
        guidance_scale,
        seed,
        offload_mode,
        vram_threshold,
        enable_kv_cache,
        clean_vram_before,
        unload_after_generate,
    ):
        # --- Pre-flight checks ------------------------------------------------
        if not _check_diffusers():
            raise RuntimeError(
                "NucleusMoEImagePipeline is not available in your diffusers "
                "installation.\n"
                "You need diffusers >= 0.38 (main branch).\n"
                "Install with:\n"
                "  pip install git+https://github.com/huggingface/diffusers\n"
                "Also install: transformers accelerate huggingface_hub sentencepiece"
            )

        # --- Clear VRAM cache if requested ------------------------------------
        if clean_vram_before:
            try:
                import comfy.model_management
                comfy.model_management.soft_empty_cache()
                logger.info("[Nucleus-Image] Cleared ComfyUI VRAM cache.")
            except ImportError:
                pass

        # --- Auto-download model (if necessary) --------------------------------
        _ensure_model(MODEL_DIR, MODEL_REPO_ID)

        # --- Load / retrieve pipeline -----------------------------------------
        pipe = _load_pipeline(MODEL_DIR, offload_mode, enable_kv_cache, vram_threshold)

        # --- Generation --------------------------------------------------------
        logger.info(
            "[Nucleus-Image] Generating: %dx%d | %d steps | CFG %.1f | seed %d",
            width, height, steps, guidance_scale, seed,
        )

        # Generator device: CPU is always safe (the pipeline handles placement)
        generator = torch.Generator(device="cpu").manual_seed(seed)

        # ComfyUI progress bar
        step_callback = None
        try:
            import comfy.utils
            pbar = comfy.utils.ProgressBar(steps)

            def step_callback(pipe_obj, step_index, timestep, callback_kwargs):
                pbar.update(1)
                return callback_kwargs
        except ImportError:
            pass

        # Prepare call kwargs
        call_kwargs = dict(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            generator=generator,
        )
        if negative_prompt.strip():
            call_kwargs["negative_prompt"] = negative_prompt.strip()
        if step_callback is not None:
            call_kwargs["callback_on_step_end"] = step_callback

        result = pipe(**call_kwargs)

        # --- Convert output to ComfyUI IMAGE format (BHWC float32 [0,1]) ------
        pil_image = result.images[0]
        image_np = np.array(pil_image).astype(np.float32) / 255.0
        image_tensor = torch.from_numpy(image_np).unsqueeze(0)  # (1, H, W, C)

        # --- Info string -------------------------------------------------------
        neg_info = f" | neg: '{negative_prompt[:40]}…'" if negative_prompt.strip() else ""
        cache_info = " | KV-cache ON" if enable_kv_cache else ""
        info = (
            f"Nucleus-Image | {width}x{height} | {steps} steps | "
            f"CFG {guidance_scale} | seed {seed}{neg_info}{cache_info} | "
            f"offload: {offload_mode}"
        )
        logger.info("[Nucleus-Image] %s", info)

        # --- Optionally unload after generation ---------------------------------
        if unload_after_generate:
            _unload_pipeline()

        return (image_tensor, info)
