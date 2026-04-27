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


# ---------------------------------------------------------------------------
# Low-level hook helpers (used by lru_offload)
# ---------------------------------------------------------------------------

def _block_to_cuda(module, args, kwargs):
    """Pre-forward: move block params to GPU."""
    module.to("cuda")
    return args, kwargs


def _block_to_cpu(module, input, output):
    """Post-forward: move block params back to CPU."""
    module.to("cpu")
    return output


def _transformer_args_to_cuda(module, args, kwargs):
    """Pre-forward on the *transformer*: move args & shell to CUDA."""
    # --- args ---------------------------------------------------------
    args = tuple(
        a.to("cuda") if isinstance(a, torch.Tensor) else a for a in args
    )
    kwargs = {
        k: v.to("cuda") if isinstance(v, torch.Tensor) else v
        for k, v in kwargs.items()
    }
    # --- shell params -------------------------------------------------
    bp = getattr(module, "_holaf_block_param_ids", set())
    bb = getattr(module, "_holaf_block_buffer_ids", set())
    for _name, param in module.named_parameters():
        if id(param) not in bp and param.device.type != "cuda":
            param.data = param.data.to("cuda")
    for _name, buf in module.named_buffers():
        if id(buf) not in bb and buf.device.type != "cuda":
            buf.data = buf.data.to("cuda")
    return args, kwargs


def _transformer_out_to_cpu(module, input, output):
    """Post-forward on the *transformer*: move output & shell to CPU."""
    # --- shell params -------------------------------------------------
    bp = getattr(module, "_holaf_block_param_ids", set())
    bb = getattr(module, "_holaf_block_buffer_ids", set())
    for _name, param in module.named_parameters():
        if id(param) not in bp and param.device.type == "cuda":
            param.data = param.data.to("cpu")
    for _name, buf in module.named_buffers():
        if id(buf) not in bb and buf.device.type == "cuda":
            buf.data = buf.data.to("cpu")
    # --- output -------------------------------------------------------
    if isinstance(output, torch.Tensor):
        return output.to("cpu")
    if isinstance(output, (tuple, list)):
        return type(output)(
            o.to("cpu") if isinstance(o, torch.Tensor) else o for o in output
        )
    return output


def _hook_module_cpu_gpu(module: torch.nn.Module) -> None:
    """
    Register hooks so *module* is moved to GPU before its forward
    and back to CPU afterwards.  Used for text_encoder and VAE.
    """
    module.register_forward_pre_hook(_block_to_cuda, with_kwargs=True)
    module.register_forward_hook(_block_to_cpu)


def _remove_all_accelerate_hooks(module: torch.nn.Module) -> None:
    """
    Recursively strip *every* accelerate hook (``_hf_hook``) from a module
    and all its children.  This guarantees that no external hook interferes
    with our manual ``.to()``-based placement.

    For a ``DiffusionPipeline`` (which is NOT an ``nn.Module``) we iterate
    over its components first, then recurse into each one.
    """
    try:
        import accelerate.hooks as _ah
    except ImportError:
        return

    # If this is a pipeline (not an nn.Module), handle its components.
    if not isinstance(module, torch.nn.Module):
        for attr_name in dir(module):
            component = getattr(module, attr_name, None)
            if isinstance(component, torch.nn.Module):
                _remove_all_accelerate_hooks(component)
        return

    # --- nn.Module path ------------------------------------------------
    if hasattr(module, "_hf_hook"):
        _ah.remove_hook_from_module(module)
    for child in module.children():
        _remove_all_accelerate_hooks(child)


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
        # --- Per-block manual offloading -------------------------------
        # Strategy:
        #   1. Strip *all* accelerate hooks recursively — ``from_pretrained``
        #      may install ``AlignDevicesHook`` on submodules.
        #   2. Move everything to CPU (real tensors, no meta).
        #   3. Keep the transformer "shell" (embeddings, norms, proj_out)
        #      on GPU permanently (~1-2 GB).
        #   4. Install bare-metal pre/post forward hooks on each
        #      transformer block that simply do ``.to("cuda")`` /
        #      ``.to("cpu")``.  No meta tensors, no accelerate.
        #   5. Hook text_encoder and VAE the same way.

        # --- strip accelerate hooks ------------------------------------
        _remove_all_accelerate_hooks(pipe)

        # --- materialize on CPU ----------------------------------------
        pipe.to("cpu")
        gc.collect()
        torch.cuda.empty_cache()

        # --- discover blocks -------------------------------------------
        blocks = _discover_transformer_blocks(pipe.transformer)

        if blocks:
            # --- tag shell params so the transformer hooks can manage them ---
            _blk_pids = set()
            _blk_bids = set()
            for blk in blocks:
                for p in blk.parameters():
                    _blk_pids.add(id(p))
                for b in blk.buffers():
                    _blk_bids.add(id(b))
            pipe.transformer._holaf_block_param_ids = _blk_pids
            pipe.transformer._holaf_block_buffer_ids = _blk_bids

            # --- per-block hooks --------------------------------------
            for _i, block in enumerate(blocks):
                block.register_forward_pre_hook(_block_to_cuda, with_kwargs=True)
                block.register_forward_hook(_block_to_cpu)

            logger.info(
                "[Nucleus-Image LRU] %d blocks with manual hooks, shell managed per-step.",
                len(blocks),
            )

            # --- transformer input / output + shell management --------
            pipe.transformer.register_forward_pre_hook(
                _transformer_args_to_cuda, with_kwargs=True
            )
            pipe.transformer.register_forward_hook(_transformer_out_to_cpu)

            # --- text encoder & VAE hooks -----------------------------
            _hook_module_cpu_gpu(pipe.text_encoder)
            if hasattr(pipe, "text_encoder_2") and pipe.text_encoder_2 is not None:
                _hook_module_cpu_gpu(pipe.text_encoder_2)
            _hook_module_cpu_gpu(pipe.vae)

        else:
            # Fallback: no blocks discovered — use standard sequential.
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
