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
- Resolution presets matching the model's training aspect ratios
- Negative prompt support
- Text KV caching for faster inference
- Multiple VRAM offloading strategies
- ComfyUI progress bar integration

Requirements
------------
    pip install git+https://github.com/huggingface/diffusers
    pip install transformers>=4.57 accelerate huggingface_hub sentencepiece

The ``NucleusMoEImagePipeline`` class is only available in diffusers >= 0.38
(main branch as of April 2026).  The stable 0.37 release does NOT include it.
"""

import os
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

# Resolution presets — these are the exact aspect ratios the model was trained
# on.  Using non-standard resolutions may produce degraded results.
RESOLUTION_PRESETS = {
    "1:1  (1024x1024)":  (1024, 1024),
    "16:9 (1344x768)":   (1344, 768),
    "9:16 (768x1344)":   (768, 1344),
    "4:3  (1184x896)":   (1184, 896),
    "3:4  (896x1184)":   (896, 1184),
    "3:2  (1248x832)":   (1248, 832),
    "2:3  (832x1248)":   (832, 1248),
    "Custom":            None,
}

# Module-level pipeline cache — survives across node invocations within the
# same process so the model is only loaded once.
_cached_pipeline = None
_cached_offload_mode = None
_cached_kv_cache = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_diffusers():
    """Verify that the required diffusers version is installed."""
    try:
        import diffusers
        from diffusers import NucleusMoEImagePipeline  # noqa: F401
        return True
    except ImportError:
        return False


def _ensure_model(model_dir: str, repo_id: str):
    """Download the model from HuggingFace Hub if not already present locally.

    Uses ``huggingface_hub.snapshot_download`` for resumable, verifiable
    downloads.  On subsequent calls, if ``model_index.json`` is found the
    download is skipped (the snapshot function would also skip existing files
    but the sentinel check avoids a network round-trip).
    """
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


def _load_pipeline(model_dir: str, offload_mode: str, enable_kv_cache: bool):
    """Load (or return cached) DiffusionPipeline.

    The pipeline is cached at the module level.  If the ``offload_mode`` or
    ``enable_kv_cache`` settings change, the cached pipeline is discarded and
    reloaded with the new settings.
    """
    global _cached_pipeline, _cached_offload_mode, _cached_kv_cache

    # Reuse cached pipeline when settings are identical
    if _cached_pipeline is not None:
        if _cached_offload_mode == offload_mode and _cached_kv_cache == enable_kv_cache:
            logger.info("[Nucleus-Image] Reusing cached pipeline.")
            return _cached_pipeline
        # Settings changed — free the old pipeline
        logger.info(
            "[Nucleus-Image] Settings changed (offload: %s->%s, kv_cache: %s->%s). "
            "Reloading pipeline.",
            _cached_offload_mode, offload_mode,
            _cached_kv_cache, enable_kv_cache,
        )
        del _cached_pipeline
        _cached_pipeline = None
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
    if offload_mode == "smart_offload":
        # Moves each component to GPU only when needed, then back to CPU.
        # Peak VRAM ≈ size of largest component (transformer ~34 GB bf16).
        pipe.enable_model_cpu_offload()
        logger.info("[Nucleus-Image] VRAM mode: smart offload (components on-demand).")
    elif offload_mode == "sequential_offload":
        # Moves individual layers to GPU one at a time.
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

    return pipe


def _unload_pipeline():
    """Fully unload the cached pipeline and free GPU memory."""
    global _cached_pipeline, _cached_offload_mode, _cached_kv_cache
    if _cached_pipeline is not None:
        del _cached_pipeline
        _cached_pipeline = None
        _cached_offload_mode = None
        _cached_kv_cache = None
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
                "resolution_preset": (
                    list(RESOLUTION_PRESETS.keys()),
                    {"default": "1:1  (1024x1024)"},
                ),
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
                    ["smart_offload", "sequential_offload", "full_gpu"],
                    {"default": "smart_offload"},
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
        resolution_preset,
        width,
        height,
        steps,
        guidance_scale,
        seed,
        offload_mode,
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
        pipe = _load_pipeline(MODEL_DIR, offload_mode, enable_kv_cache)

        # --- Determine resolution ----------------------------------------------
        if resolution_preset != "Custom":
            width, height = RESOLUTION_PRESETS[resolution_preset]

        # --- Generation --------------------------------------------------------
        logger.info(
            "[Nucleus-Image] Generating: %dx%d | %d steps | CFG %.1f | seed %d",
            width, height, steps, guidance_scale, seed,
        )

        # The generator device: use CPU for offloaded models (avoids device-mismatch
        # issues in pipelines that create initial noise on the model's device).
        gen_device = "cuda" if offload_mode == "full_gpu" else "cpu"
        generator = torch.Generator(device=gen_device).manual_seed(seed)

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

        # Prepare call kwargs (drop empty negative_prompt to avoid unnecessary
        # text-encoder overhead)
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
