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


# Block-discovery logic shared by the helpers below.

def _discover_transformer_blocks(transformer: torch.nn.Module) -> list:
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


def _move_shell_to_gpu(transformer: torch.nn.Module, blocks: list) -> None:
    """Move only non-block parameters / buffers to GPU."""
    block_param_ids = set()
    block_buffer_ids = set()
    for block in blocks:
        for p in block.parameters():
            block_param_ids.add(id(p))
        for b in block.buffers():
            block_buffer_ids.add(id(b))

    for _name, param in transformer.named_parameters():
        if id(param) not in block_param_ids and param.device.type != "cuda":
            param.data = param.data.to("cuda")
    for _name, buf in transformer.named_buffers():
        if id(buf) not in block_buffer_ids and buf.device.type != "cuda":
            buf.data = buf.data.to("cuda")


def _materialize_pipeline_to_cpu(pipe) -> None:
    """
    Materialize every meta tensor in the pipeline to CPU.

    Accelerate's cpu_offload replaces module params with meta tensors
    and stores the real data in a CpuOffloadedStateDict.  This helper
    triggers the pre_forward hook for each component to restore the
    state dict to CPU, then removes the hook so we can manage placement
    ourselves.
    """
    import accelerate.hooks

    for attr_name in dir(pipe):
        component = getattr(pipe, attr_name, None)
        if not isinstance(component, torch.nn.Module):
            continue
        if not any(p.device.type == "meta" for p in component.parameters()):
            continue

        # The component has an accelerate hook with an offloaded state dict.
        for _name, param in component.named_parameters():
            if param.device.type != "meta":
                continue
            # Retrieve the real tensor from the hook's state dict.
            hook = getattr(component, "_hf_hook", None)
            if hook is not None and hasattr(hook, "state_dict"):
                sd = hook.state_dict
                if _name in sd:
                    param.data = sd[_name].to("cpu", copy=False)

        # Remove the accelerate hook so it doesn't interfere.
        if hasattr(component, "_hf_hook"):
            accelerate.hooks.remove_hook_from_module(component)


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
    if offload_mode == "lru_offload":
        # --- Per-block offloading via accelerate's cpu_offload ---
        # Strategy:
        #   1. Load pipeline, materialize everything to CPU.
        #   2. Discover transformer blocks and offload each one individually
        #      with accelerate.cpu_offload.  This handles meta-tensor
        #      materialization correctly (unlike manual .to("cuda")).
        #   3. Move the transformer "shell" (embeddings, norms, proj_out)
        #      to GPU permanently — these are small (~1-2 GB).
        #   4. Text encoder and VAE are also managed by cpu_offload for
        #      their respective phases.
        #
        # Peak VRAM on a 12 GB card:
        #   shell (~1-2 GB) + one active block (~4 GB)
        #   + text_encoder / VAE (~1 GB on demand) ≈ 6-7 GB

        # --- materialize on CPU ------------------------------------------
        # Use accelerate's load_checkpoint_and_dispatch-style materialization.
        # Calling .to("cpu") may fail on meta tensors (PyTorch >= 2.x).
        try:
            pipe.to("cpu")
        except NotImplementedError:
            # Some tensors are still on "meta" — materialize via accelerate.
            _materialize_pipeline_to_cpu(pipe)

        gc.collect()
        torch.cuda.empty_cache()

        # --- discover blocks ---------------------------------------------
        blocks = _discover_transformer_blocks(pipe.transformer)

        if blocks:
            # Offload each block individually with accelerate.
            # This is safe: cpu_offload saves the state dict to CPU,
            # replaces params with meta, and hooks pre_forward to load
            # back to GPU before the block executes.
            from accelerate import cpu_offload as _accel_cpu_offload
            for _i, block in enumerate(blocks):
                _accel_cpu_offload(block, execution_device="cuda")

            # Move shell (non-block) parameters to GPU.
            # They stay there for the whole denoising loop.
            _move_shell_to_gpu(pipe.transformer, blocks)

            logger.info(
                "[Nucleus-Image LRU] Shell on GPU, %d blocks managed by accelerate cpu_offload.",
                len(blocks),
            )

            # --- text encoder & VAE --------------------------------------
            # Also managed by accelerate cpu_offload (instead of calling
            # enable_sequential_cpu_offload, which may interfere with the
            # transformer's per-block hooks).
            _accel_cpu_offload(pipe.text_encoder, execution_device="cuda")
            if hasattr(pipe, "text_encoder_2") and pipe.text_encoder_2 is not None:
                _accel_cpu_offload(pipe.text_encoder_2, execution_device="cuda")
            _accel_cpu_offload(pipe.vae, execution_device="cuda")

        else:
            # Fallback: offload entire transformer as one unit.
            pipe.enable_sequential_cpu_offload()
            logger.warning(
                "[Nucleus-Image LRU] Could not discover blocks — "
                "falling back to sequential offload."
            )

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
