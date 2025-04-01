# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-01
#
# Purpose:
# This file defines the 'UpscaleImageHolaf' custom node for ComfyUI.
# It provides functionality to upscale an input image using a specified
# upscaling model (e.g., ESRGAN, SwinIR) loaded via Spandrel, targeting a
# final resolution defined by a desired megapixel count.
#
# Design Choices & Rationale:
# - Megapixel Targeting: Instead of a fixed scale factor, the user specifies
#   the desired output resolution in megapixels. The node calculates the
#   required target width and height to achieve this while preserving the
#   original aspect ratio.
# - Spandrel Model Loading: Leverages the `spandrel` library (via `ModelLoader`
#   and `comfy.utils.load_torch_file`) for loading various upscale model
#   architectures from state dictionaries found in the `upscale_models` folder.
#   This provides compatibility with many common upscaler types.
# - Tiled Upscaling (`comfy.utils.tiled_scale`): Utilizes ComfyUI's built-in
#   `tiled_scale` utility function. This function automatically handles breaking
#   the image into tiles if necessary (based on default tile size/overlap or
#   potential future configuration), processing each tile with the model, and
#   stitching the results back together. This is crucial for handling large
#   images that might exceed GPU memory if processed whole.
# - Two-Stage Scaling (Model Scale + Resampling):
#   1. Model Upscaling: The image is first upscaled using the selected model's
#      native scale factor within `tiled_scale`.
#   2. Resampling (if needed): After the model upscale, the node checks if the
#      resulting image dimensions match the target dimensions calculated from the
#      `megapixels` input. If they differ, it performs a second scaling step
#      using a standard resampling algorithm (selected via `upscale_method`, e.g.,
#      'lanczos', 'bicubic') to resize the image precisely to the target dimensions.
#      This ensures the final output matches the desired megapixel count, even if
#      the model's scale factor doesn't align perfectly.
# - Device Management: Relies on `comfy.model_management` and `comfy.utils.tiled_scale`
#   to handle device placement (moving model and data to GPU for processing,
#   results back to CPU).
# - Error Handling: Includes checks for missing model files and catches potential
#   errors during model loading and the upscaling process.
# - Output: Returns the final upscaled image and the name of the model used as a string.
# === End Documentation ===

import torch
import folder_paths
import comfy.model_management
import comfy.utils
from spandrel import ModelLoader # Import ModelLoader from spandrel
from nodes import ImageScale # Using ImageScale for potential resampling if needed

class UpscaleImageHolaf:
    """
    Custom node to upscale an image using an upscaling model, targeting a specific megapixel count.
    Mimics the functionality of ComfyUI's core ImageUpscaleWithModel node but with a custom name and category.
    Includes an output for the model name used.
    """
    upscale_methods = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]
    # crop_methods = ["disabled", "center"] # Crop is not shown in the UI image, omitting for now

    @classmethod
    def INPUT_TYPES(s):
        # Ensure upscale_models folder exists and list models
        if not folder_paths.folder_names_and_paths["upscale_models"]:
             print("Warning: No upscale_models folder found.")
             upscale_model_list = ["None"]
        else:
             upscale_model_list = folder_paths.get_filename_list("upscale_models")
             if not upscale_model_list:
                  print("Warning: No models found in upscale_models folder.")
                  upscale_model_list = ["None"]

        return {
            "required": {
                "image": ("IMAGE",),
                "model_name": (upscale_model_list, ),
                "upscale_method": (s.upscale_methods,), # Included as per image, role might be for resampling
                "megapixels": ("FLOAT", {"default": 2.00, "min": 0.01, "max": 16.00, "step": 0.01}), # Max 16MP is arbitrary but reasonable
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("IMAGE", "MODEL_NAME_TEXT")
    FUNCTION = "upscale"
    CATEGORY = "Holaf" # Assigning to the Holaf category

    def upscale(self, image, model_name, upscale_method, megapixels):
        if model_name == "None" or not model_name:
             print("Upscale (Holaf): No model selected, passing image through.")
             return (image, "None")

        model_path = folder_paths.get_full_path("upscale_models", model_name)
        if not model_path:
            raise FileNotFoundError(f"Upscale model not found: {model_name}")

        # Load upscale model using spandrel, similar to core ComfyUI nodes
        device = comfy.model_management.get_torch_device()
        try:
            print(f"Upscale (Holaf): Loading state dict for {model_name}...")
            sd = comfy.utils.load_torch_file(model_path, safe_load=True)
            # Optional: Handle potential state dict prefix issues (common in some models)
            if "module.layers.0.residual_group.blocks.0.norm1.weight" in sd:
                 print(f"Upscale (Holaf): Removing 'module.' prefix from state dict keys for {model_name}.")
                 sd = comfy.utils.state_dict_prefix_replace(sd, {"module.":""})

            print(f"Upscale (Holaf): Instantiating model {model_name} using Spandrel...")
            upscale_model_descriptor = ModelLoader().load_from_state_dict(sd)

            # Ensure it's a valid image model descriptor (Spandrel specific)
            # Note: The core node doesn't explicitly check this here, but relies on the loader node type.
            # We assume ModelLoader handles basic validation.

            # Get the actual model instance from the descriptor
            upscale_model = upscale_model_descriptor.model

            # Put the model into evaluation mode
            upscale_model.eval()

            # Don't use load_model_gpu here, as the Spandrel model object might not be compatible.
            # Device placement will happen just before use in tiled_upscale.
            print(f"Upscale (Holaf): Successfully loaded upscale model '{model_name}' using Spandrel.")

        except Exception as e:
            print(f"Error loading upscale model {model_name} using Spandrel: {e}")
            raise RuntimeError(f"Failed to load upscale model: {model_name}") from e


        # Calculate target dimensions based on megapixels
        batch_size, original_height, original_width, _ = image.shape
        original_pixels = original_height * original_width
        # Target pixels: megapixels * 1,048,576 (1024*1024)
        target_pixels = megapixels * 1048576.0

        if target_pixels <= 0:
             raise ValueError("Megapixels must be positive.")
        if original_pixels <= 0:
             print("Warning: Input image has zero area.")
             return (image, model_name) # Pass through if input is invalid

        scale_factor = (target_pixels / original_pixels) ** 0.5

        if scale_factor <= 0:
             raise ValueError("Calculated scale factor is invalid (must be > 0).")

        # Target dimensions (integer)
        target_width = max(1, int(original_width * scale_factor))
        target_height = max(1, int(original_height * scale_factor))

        print(f"Upscale (Holaf): Scaling from {original_width}x{original_height} to target {target_width}x{target_height} ({megapixels:.2f} MP) using {model_name}")

        # Permute image to NCHW format for model processing
        image_for_model = image.movedim(-1, 1)

        # Upscale using the model, potentially with tiling
        # Using comfy's tiled_upscale utility handles tiling automatically
        # Note: upscale_amount is derived from target size, not directly used by tiled_upscale if model dictates size.
        # We let the model upscale and then potentially resize if needed.
        try:
            with torch.no_grad():
                 # tiled_scale handles device placement and potential OOM
                 # Ensure the model is on the correct device before passing to tiled_scale
                 upscale_model.to(device)
                 # Get the model's native scale factor
                 model_scale = upscale_model_descriptor.scale # Use scale from Spandrel descriptor

                 # Use tiled_scale, similar to the core node
                 scaled_img = comfy.utils.tiled_scale(
                      image_for_model,
                      # Pass the model's forward pass.
                      # The lambda function handles moving data for the model call.
                      lambda x: upscale_model(x.to(device)).cpu(), # Model output should be moved to CPU
                      tile_x=512, # Default tile size, consider making configurable later
                      tile_y=512,
                      overlap=64, # Default overlap, consider making configurable later
                      upscale_amount=model_scale, # Use the model's actual scale factor
                      # out_channels is not a parameter for tiled_scale
                      pbar=None # No progress bar for now
                 )
        except Exception as e:
             print(f"Error during model upscale: {e}")
             # Consider releasing model memory here if needed
             raise RuntimeError(f"Failed to upscale image using model {model_name}") from e
        finally:
             # Optional: Move model back to CPU/intermediate device if managing manually
             # comfy.model_management usually handles this based on memory pressure
             pass


        # Permute back to NHWC format for ComfyUI
        upscaled_image = scaled_img.movedim(1, -1)

        # Optional: Check if the output size matches the target and resize if necessary
        current_height, current_width = upscaled_image.shape[1], upscaled_image.shape[2]
        if current_width != target_width or current_height != target_height:
             print(f"Upscale (Holaf): Model output size ({current_width}x{current_height}) differs from target ({target_width}x{target_height}). Resampling with '{upscale_method}'.")
             # Use ImageScale logic for precise resizing
             resizer = ImageScale()
             # ImageScale expects NHWC, which we have now
             upscaled_image = resizer.upscale(upscaled_image, upscale_method, target_width, target_height, "disabled")[0]


        return (upscaled_image, model_name)
