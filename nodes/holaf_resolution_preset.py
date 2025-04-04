# === Documentation ===
# Author: Cline (AI Assistant) / Original comments by User/Cline
# Date: 2025-04-01
#
# Purpose:
# This file defines the 'HolafResolutionPreset' custom node for ComfyUI.
# Its goal is to simplify setting optimal image dimensions (width, height)
# for image generation workflows, particularly when targeting specific
# Stable Diffusion models (SD1.5, SDXL, FLUX) which have recommended
# native resolutions for best performance.
#
# Design Choices & Rationale:
# - Combined Approach: Instead of just selecting a model or a ratio, the node
#   combines both. The user selects a standard aspect ratio (e.g., "16:9 Landscape")
#   and a target model type (e.g., "SDXL").
# - Optimal Resolution Matching: The node then finds the predefined, recommended
#   resolution for the selected model that most closely matches the chosen
#   aspect ratio *and* its orientation (portrait/landscape/square).
# - Avoiding Suboptimal Scaling: This prevents simply scaling a base resolution
#   (like 1024x1024) to fit a ratio, which might result in dimensions not ideal
#   for the model's training.
# - Predefined Data: Uses hardcoded lists (`SD15_RESOLUTIONS`, `SDXL_RESOLUTIONS`,
#   `FLUX_RESOLUTIONS`) containing tuples of (width, height, pre-calculated_ratio)
#   for known good dimensions for each model type. FLUX resolutions are specifically
#   calculated to meet its unique constraints while matching standard ratios.
# - User-Friendly Ratios: Employs a dictionary (`ASPECT_RATIOS`) mapping common,
#   human-readable ratio names (including orientation) to their numerical values. Includes "Random".
# - Matching Logic:
#   1. Determines the target aspect ratio: from optional input image if `use_image_ratio` is True,
#      otherwise from the dropdown (handling "Random" selection).
#   2. Retrieves the list of resolutions for the selected model.
#   3. Determines the target orientation (portrait/square/landscape) based on the target ratio.
#   4. Filters the model's resolutions to only include those matching the target orientation.
#   5. Tries to find a predefined resolution with an *exact* ratio match (within tolerance).
#   6. If an exact match is found, it's returned.
#   7. If no exact match, it *calculates* a new resolution:
#      a. Starts with the largest dimension found in the predefined list for that model.
#      b. Calculates the other dimension to match the target aspect ratio.
#      c. Scales the dimensions proportionally to fit within a target megapixel range
#         specific to the model (e.g., 1-1.5MP for SDXL).
#      d. Rounds the final dimensions to the nearest multiple required by the model
#         (e.g., multiple of 8 for SDXL/FLUX, 64 for SD1.5), ensuring a minimum size.
# - Fallback: Includes a basic fallback mechanism if no resolutions match the
#   target orientation *before* calculation (returns the first resolution listed for the model).
# - Optional Image Input: Allows providing an image to derive the target aspect ratio
#   instead of using the dropdown, controlled by a boolean toggle (`use_image_ratio`).
# - Cache Busting (`IS_CHANGED`): Forces re-execution when "Random" is selected or when
#   `use_image_ratio` is True and the input image might have changed (based on shape).
# === End Documentation ===
import math
import sys # For float epsilon comparison
import random # Added for random ratio selection
import torch # Added for image tensor handling

# --- Data ---
# Define recommended/native resolutions for different Stable Diffusion models.
# Each tuple represents (width, height, aspect_ratio).
# Aspect ratio is pre-calculated for efficient comparison later.

# Resolutions commonly used or trained for SD 1.5 models
SD15_RESOLUTIONS = [
    (512, 512, 1.0),           # Square 1:1
    (768, 512, 1.5),           # Landscape 3:2
    (512, 768, 512/768),       # Portrait 2:3 (~0.67)
]

# Resolutions recommended by Stability AI for SDXL 1.0
# Source: https://stability.ai/blog/sdxl-1024-resolutions
SDXL_RESOLUTIONS = [
    (1024, 1024, 1.0),         # Square 1:1
    (1152, 896, 1152/896),     # Landscape ~1.29
    (896, 1152, 896/1152),     # Portrait ~0.78
    (1216, 832, 1216/832),     # Landscape ~1.46
    (832, 1216, 832/1216),     # Portrait ~0.68
    (1344, 768, 1344/768),     # Landscape 1.75 (16:9)
    (768, 1344, 768/1344),     # Portrait ~0.57 (9:16)
    (1536, 640, 1536/640),     # Landscape 2.4 (~21:9)
    (640, 1536, 640/1536),     # Portrait ~0.42 (~9:21)
]

# Resolutions for FLUX. Unlike SD1.5/SDXL's fixed native resolutions,
# FLUX allows more flexibility (e.g., dimensions based on 768/1024/1600/1920,
# multiples of 8, total pixels ~1M-2M).
# This list provides pre-calculated presets that match standard aspect ratios
# while respecting these constraints, offering a user-friendly approach.
FLUX_RESOLUTIONS = [
    (896, 1600, 896/1600),     # Match for 9:16 Portrait (~0.56)
    (1024, 1536, 1024/1536),    # Match for 2:3 Portrait (~0.67)
    (1200, 1600, 1200/1600),    # Match for 3:4 Portrait (0.75)
    (1024, 1280, 1024/1280),    # Match for 4:5 Portrait (0.8)
    (1024, 1024, 1.0),         # Match for 1:1 Square (1.0)
    (1280, 1024, 1280/1024),    # Match for 5:4 Landscape (1.25)
    (1600, 1200, 1600/1200),    # Match for 4:3 Landscape (~1.33)
    (1536, 1024, 1536/1024),    # Match for 3:2 Landscape (1.5)
    (1824, 1024, 1824/1024),    # Match for 16:9 Landscape (~1.78)
    (1832, 768, 1832/768),     # Match for ~2.39:1 Landscape (~2.39)
]

# --- Model Specific Constraints ---

# Target megapixel ranges (min_pixels, max_pixels)
MODEL_MP_RANGES = {
    "SD1.5": (250000, 600000),
    "SDXL": (1000000, 1500000),
    "FLUX": (1000000, 2000000),
}

# Rounding multiple requirement
MODEL_ROUNDING = {
    "SD1.5": 64,
    "SDXL": 8,
    "FLUX": 8,
}

# Maximum dimension found in the predefined lists (used as base for calculation)
MODEL_MAX_DIMS = {
    "SD1.5": 768,  # max(512, 768)
    "SDXL": 1536, # max(1024, 1152, 896, 1216, 832, 1344, 768, 1536, 640)
    "FLUX": 1832, # max(896, 1600, 1024, 1536, 1200, 1280, 1600, 1824, 1832, 768)
}

# Tolerance for floating point ratio comparison
RATIO_TOLERANCE = sys.float_info.epsilon * 10 # A small tolerance

# Dictionary mapping model type identifiers (used in the UI dropdown)
# to their corresponding list of recommended resolutions.
MODEL_RESOLUTIONS = {
    "SD1.5": SD15_RESOLUTIONS,
    "SDXL": SDXL_RESOLUTIONS,
    "FLUX": FLUX_RESOLUTIONS, # Added FLUX resolutions
    # Add other models here in the future if needed
}

# Dictionary defining standard aspect ratios commonly used in photography/cinematography.
# Keys are human-readable names (used in the UI dropdown).
# Values are the numerical aspect ratio (width / height).
# Including orientation in the name helps disambiguate (e.g., 2:3 vs 3:2).
ASPECT_RATIOS = {
    "9:16 Portrait (Mobile Video)": 9/16,       # 0.5625
    "2:3 Portrait (35mm Photo)": 2/3, # ~0.6667
    "3:4 Portrait (Classic Monitor-Photo)": 3/4,         # 0.75
    "4:5 Portrait (Large Format Photo)": 4/5,         # 0.8
    "1:1 Square (Instagram-Medium Format)": 1.0,
    "5:4 Landscape (Large Format Photo)": 5/4,         # 1.25
    "4:3 Landscape (Classic Monitor-Photo)": 4/3,         # ~1.3333
    "3:2 Landscape (35mm Photo)": 3/2, # 1.5
    "16:9 Landscape (HD Video-Widescreen)": 16/9, # ~1.7778
    "~2.39:1 Landscape (Anamorphic Cinema)": 2.39, # Approximation for common cinematic wide formats
    "Random": None, # Placeholder for random selection
}

# --- Node Class ---
# Defines the main logic and properties of the ComfyUI node.
class HolafResolutionPreset:
    @classmethod
    def INPUT_TYPES(cls):
        """
        Defines the input fields presented in the ComfyUI node interface.
        'required' inputs must be provided for the node to function.
        'optional' inputs are not strictly necessary but provide additional features.
        """
        return {
            "required": {
                "model_type": (list(MODEL_RESOLUTIONS.keys()),),
                "aspect_ratio": (["Random"] + [k for k in ASPECT_RATIOS.keys() if k != "Random"],),
                "use_image_ratio": ("BOOLEAN", {"default": False}), # Toggle to use image ratio
            },
            "optional": {
                 "image": ("IMAGE",), # Optional image input
            }
        }

    # Define the data types of the outputs provided by the node.
    RETURN_TYPES = ("INT", "INT")
    # Define the names of the outputs (used for connecting to other nodes).
    RETURN_NAMES = ("width", "height")
    # Specifies the method within this class that executes the node's logic.
    FUNCTION = "get_resolution"
    # Defines the category under which this node will appear in the ComfyUI menu.
    CATEGORY = "Holaf" # Changed from _for_testing

    def IS_CHANGED(self, model_type, aspect_ratio, use_image_ratio, image=None):
        """
        Forces re-execution if 'Random' is selected or if using image ratio and the image changes.
        ComfyUI calls this method to check if the node's output might change even if inputs seem the same.
        Returning a different value each time signals a change.
        """
        if aspect_ratio == "Random":
            # Return a constantly changing value to force re-run when Random is selected
            return random.random()

        # If using image ratio, check if the image itself has changed.
        # We use the image tensor's shape as a proxy for change.
        # This assumes the upstream node providing the image correctly implements IS_CHANGED.
        image_hash = "no_image"
        if use_image_ratio and image is not None and isinstance(image, torch.Tensor):
            image_hash = hash(image.shape)

        # Return a stable value based on all relevant inputs for normal caching
        return f"{model_type}-{aspect_ratio}-{use_image_ratio}-{image_hash}"

    def _round_to_multiple(self, value, multiple):
        """Rounds value to the nearest multiple, ensuring it's at least the multiple."""
        if multiple == 0:
            return max(1, round(value)) # Avoid division by zero, return rounded value >= 1
        # Corrected line: ensure it's max(multiple, ...)
        return max(multiple, round(value / multiple) * multiple)

    def get_resolution(self, model_type, aspect_ratio, use_image_ratio, image=None):
        """
        Core logic:
        1. Determines the target aspect ratio (from dropdown, random, or input image).
        2. Tries to find an exact predefined resolution match for the ratio and orientation.
        3. If not found, calculates a resolution based on max dimension, target ratio,
           megapixel constraints, and rounding rules.
        """
        target_ratio = None
        source_description = "" # For logging

        # 0. Determine the source of the target ratio
        if use_image_ratio and image is not None:
            # Check if image is a Tensor and has the expected dimensions (N, H, W, C)
            if isinstance(image, torch.Tensor) and image.ndim == 4:
                img_height = image.shape[1]
                img_width = image.shape[2]
                if img_height > 0 and img_width > 0:
                    target_ratio = img_width / img_height
                    source_description = f"input image ({img_width}x{img_height})"
                    print(f"[HolafResolutionPreset] Using ratio from input image: {target_ratio:.4f} ({img_width}x{img_height})")
                else:
                    print("[HolafResolutionPreset] Warning: Input image has zero height or width. Ignoring.")
            else:
                 print(f"[HolafResolutionPreset] Warning: Invalid image input provided (expected Tensor NCHW, got {type(image)}). Ignoring.")

        if target_ratio is None: # If not using image ratio or image was invalid/missing
            selected_aspect_ratio_name = aspect_ratio
            if selected_aspect_ratio_name == "Random":
                available_ratio_names = [k for k in ASPECT_RATIOS.keys() if k != "Random"]
                if not available_ratio_names:
                     print("[HolafResolutionPreset] Error: No other aspect ratios available for random selection.")
                     selected_aspect_ratio_name = "1:1 Square (Instagram/Medium Format)" # Fallback
                else:
                    selected_aspect_ratio_name = random.choice(available_ratio_names)
                print(f"[HolafResolutionPreset] 'Random' selected. Using randomly chosen ratio: '{selected_aspect_ratio_name}'")
                source_description = f"randomly selected dropdown ('{selected_aspect_ratio_name}')"
                target_ratio = ASPECT_RATIOS[selected_aspect_ratio_name]
            else:
                # Check if the selected name is actually in the dictionary before accessing
                if selected_aspect_ratio_name in ASPECT_RATIOS:
                    source_description = f"dropdown ('{selected_aspect_ratio_name}')"
                    target_ratio = ASPECT_RATIOS[selected_aspect_ratio_name]
                else:
                    print(f"[HolafResolutionPreset] Warning: Selected aspect ratio '{selected_aspect_ratio_name}' not found in ASPECT_RATIOS. Falling back.")
                    # Fallback if the name somehow isn't valid (shouldn't happen with dropdown)
                    selected_aspect_ratio_name = "1:1 Square (Instagram/Medium Format)"
                    target_ratio = ASPECT_RATIOS[selected_aspect_ratio_name]
                    source_description = f"fallback dropdown ('{selected_aspect_ratio_name}')"


        if target_ratio is None: # Should not happen after fallbacks, but final safety check
            print("[HolafResolutionPreset] Error: Could not determine target ratio. Falling back to 1.0.")
            target_ratio = 1.0
            source_description = "fallback (1.0)"


        # 1. Get available resolutions for the model
        available_resolutions = MODEL_RESOLUTIONS[model_type]

        # 2. Determine target orientation based on the final target_ratio
        is_portrait = target_ratio < 1.0
        is_square = abs(target_ratio - 1.0) < RATIO_TOLERANCE # Use tolerance for float comparison
        is_landscape = target_ratio > 1.0

        # 3. Filter resolutions by orientation
        filtered_resolutions = []
        for w, h, r in available_resolutions:
            res_is_portrait = r < 1.0
            res_is_square = abs(r - 1.0) < RATIO_TOLERANCE
            res_is_landscape = r > 1.0

            if (is_portrait and res_is_portrait) or \
               (is_square and res_is_square) or \
               (is_landscape and res_is_landscape):
                filtered_resolutions.append((w, h, r))

        # 4. Handle case where no resolutions match orientation (fallback)
        if not filtered_resolutions:
             print(f"[HolafResolutionPreset] Warning: No predefined resolutions found matching the orientation "
                   f"for {model_type} and ratio from {source_description}. Falling back to the first available resolution for the model.")
             fallback_res = available_resolutions[0]
             return (fallback_res[0], fallback_res[1])

        # 5. Try to find an exact match (within tolerance) in filtered list
        exact_match = None
        for w, h, r in filtered_resolutions:
            if abs(r - target_ratio) < RATIO_TOLERANCE:
                exact_match = (w, h)
                print(f"[HolafResolutionPreset] Found exact predefined match: {exact_match}")
                break # Found it, no need to search further

        if exact_match:
            return exact_match

        # 6. No exact match found - Calculate new resolution
        print(f"[HolafResolutionPreset] No exact predefined match for ratio {target_ratio:.4f} (from {source_description}). Calculating resolution...")

        # 6a. Get model constraints
        max_dim = MODEL_MAX_DIMS.get(model_type, 1024) # Default to 1024 if model unknown
        min_pixels, max_pixels = MODEL_MP_RANGES.get(model_type, (1000000, 1500000)) # Default SDXL range
        rounding = MODEL_ROUNDING.get(model_type, 8) # Default SDXL/FLUX rounding

        # 6b. Calculate initial dimensions based on max_dim and target_ratio
        if is_landscape or is_square:
            width_initial = max_dim
            height_initial = max_dim / target_ratio
        else: # Portrait
            height_initial = max_dim
            width_initial = max_dim * target_ratio

        # 6c. Adjust to fit megapixel range
        current_pixels = width_initial * height_initial
        scale_factor = 1.0

        if current_pixels < min_pixels:
            scale_factor = math.sqrt(min_pixels / current_pixels)
            print(f"[HolafResolutionPreset] Scaling up to meet min pixels ({min_pixels/1e6:.2f}MP). Scale: {scale_factor:.3f}")
        elif current_pixels > max_pixels:
            scale_factor = math.sqrt(max_pixels / current_pixels)
            print(f"[HolafResolutionPreset] Scaling down to meet max pixels ({max_pixels/1e6:.2f}MP). Scale: {scale_factor:.3f}")
        else:
             print(f"[HolafResolutionPreset] Initial pixels ({current_pixels/1e6:.2f}MP) within target range.")


        width_adjusted = width_initial * scale_factor
        height_adjusted = height_initial * scale_factor

        # 6d. Round to nearest multiple (N)
        final_width = self._round_to_multiple(width_adjusted, rounding)
        final_height = self._round_to_multiple(height_adjusted, rounding)

        print(f"[HolafResolutionPreset] Calculated Resolution: W={final_width}, H={final_height} "
              f"(Target Ratio: {target_ratio:.4f}, Final Ratio: {final_width/final_height:.4f}, "
              f"Pixels: {final_width*final_height/1e6:.2f}MP, Rounded to multiple of {rounding})")

        return (final_width, final_height)


# --- Node Mappings ---
# These dictionaries are used by ComfyUI to discover and register the node.

# Maps the node's internal class name to the class implementation.
NODE_CLASS_MAPPINGS = {
    "HolafResolutionPreset": HolafResolutionPreset
}

# Maps the node's internal class name to the display name shown in the ComfyUI menu.
NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafResolutionPreset": "Resolution Preset (Holaf)"
}
