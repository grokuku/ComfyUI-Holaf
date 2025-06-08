import torch
import folder_paths
import comfy.model_management
import comfy.utils
from spandrel import ModelLoader
from nodes import ImageScale

class UpscaleImageHolaf:
    """
    Upscales an image using a chosen model (e.g., ESRGAN) to a target
    megapixel count. This provides flexible size control, independent of the
    model's native scale factor (e.g., 4x).
    """
    upscale_methods = ["nearest-exact", "bilinear", "area", "bicubic", "lanczos"]

    @classmethod
    def INPUT_TYPES(s):
        # Dynamically populates the `model_name` dropdown with files from the `upscale_models` folder.
        try:
            upscale_model_list = folder_paths.get_filename_list("upscale_models")
            if not upscale_model_list:
                upscale_model_list = ["None"]
        except Exception:
            upscale_model_list = ["None"]
            print("Warning: Could not access upscale_models folder.")

        return {
            "required": {
                "image": ("IMAGE",),
                "model_name": (upscale_model_list, ),
                "upscale_method": (s.upscale_methods,),
                # The target output size, expressed in megapixels.
                "megapixels": ("FLOAT", {"default": 2.00, "min": 0.01, "max": 16.00, "step": 0.01}),
            }
        }

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("IMAGE", "MODEL_NAME_TEXT")
    FUNCTION = "upscale"
    CATEGORY = "Holaf"

    def upscale(self, image, model_name, upscale_method, megapixels):
        # If no model is selected, simply pass the image through without changes.
        if model_name == "None" or not model_name:
             return (image, "None")

        # --- Model Loading ---
        # Load the selected upscale model. Spandrel is used here for its broad
        # compatibility with various upscaler model architectures.
        model_path = folder_paths.get_full_path("upscale_models", model_name)
        if not model_path:
            raise FileNotFoundError(f"Upscale model not found: {model_name}")

        device = comfy.model_management.get_torch_device()
        try:
            sd = comfy.utils.load_torch_file(model_path, safe_load=True)
            upscale_model_descriptor = ModelLoader().load_from_state_dict(sd)
            upscale_model = upscale_model_descriptor.model
            upscale_model.eval()
        except Exception as e:
            raise RuntimeError(f"Failed to load upscale model '{model_name}': {e}") from e

        # --- Target Dimension Calculation ---
        # Calculate the target width and height to match the desired megapixel count
        # while preserving the original aspect ratio.
        _, original_height, original_width, _ = image.shape
        original_pixels = original_height * original_width
        target_pixels = megapixels * 1048576.0 # 1 MP = 1024*1024 pixels

        if target_pixels <= 0: raise ValueError("Megapixels must be positive.")
        if original_pixels <= 0: return (image, model_name)

        # The scale factor is the square root of the ratio of target pixels to original pixels.
        scale_factor = (target_pixels / original_pixels) ** 0.5
        target_width = max(1, int(original_width * scale_factor))
        target_height = max(1, int(original_height * scale_factor))

        # --- Two-Stage Upscaling ---
        # The upscaling is a two-stage process to handle any target size efficiently.

        # Stage 1: Upscale using the loaded model's native scale factor.
        # `comfy.utils.tiled_scale` processes the image in chunks (tiles), which is
        # essential for handling large images that would otherwise exceed VRAM limits.
        image_for_model = image.movedim(-1, 1) # Permute to NCHW for model input
        try:
            with torch.no_grad():
                 upscale_model.to(device)
                 model_scale = upscale_model_descriptor.scale
                 scaled_img = comfy.utils.tiled_scale(
                      image_for_model,
                      lambda x: upscale_model(x.to(device)).cpu(),
                      tile_x=512, tile_y=512, overlap=64,
                      upscale_amount=model_scale
                 )
        except Exception as e:
             raise RuntimeError(f"Failed to upscale image with model '{model_name}': {e}") from e

        upscaled_image = scaled_img.movedim(1, -1) # Permute back to NHWC

        # Stage 2: If the model's output size (e.g., from a fixed 4x scale) doesn't
        # perfectly match the target, perform a final resampling step (e.g., Lanczos)
        # to resize it precisely to the calculated target width and height.
        current_height, current_width = upscaled_image.shape[1:3]
        if current_width != target_width or current_height != target_height:
             resizer = ImageScale()
             upscaled_image = resizer.upscale(upscaled_image, upscale_method, target_width, target_height, "disabled")[0]

        return (upscaled_image, model_name)