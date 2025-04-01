# === Holaf Resolution Preset Node ===
#
# Author: Cline (via user request)
# Date: 2025-04-01
#
# --- Design Rationale & Goal ---
# This node aims to simplify setting image dimensions in ComfyUI workflows,
# especially when targeting specific Stable Diffusion models (like SD1.5 or SDXL)
# which perform best at certain native resolutions and aspect ratios.
#
# Initial ideas involved presets based purely on model (e.g., "SDXL 1024x1024")
# or purely on standard ratios (e.g., "16:9 Landscape").
#
# We decided on a combined approach:
# 1. User selects a standard photographic/cinematic aspect ratio (e.g., "16:9 Landscape").
# 2. User selects the target model type (e.g., "SDXL").
# 3. The node finds the *native/recommended resolution* for the selected model
#    that most closely matches the chosen aspect ratio *and* orientation (portrait/landscape/square).
#
# This approach provides user-friendly standard ratios while ensuring the output
# dimensions are optimized for the selected AI model, preventing potentially
# suboptimal dimensions that could arise from simply scaling a base resolution (like 1024)
# to match a ratio.
#
# --- Implementation Details ---
# - Stores lists of known good (width, height, ratio) tuples for each model.
# - Stores a dictionary of standard aspect ratios with user-friendly names and numerical values.
# - Filters the model's resolutions based on the orientation implied by the chosen ratio.
# - Calculates the closest match based on the numerical aspect ratio difference.
#
# --- Future Considerations ---
# - Add more model types (e.g., SD3, specific fine-tunes).
# - Allow user input for a custom "target area" (e.g., ~1 megapixel) instead of relying solely on model type.
# - Add an option to enforce dimensions being multiples of 64 (currently relies on native resolutions already being compliant).
#
import math

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

# Dictionary mapping model type identifiers (used in the UI dropdown)
# to their corresponding list of recommended resolutions.
MODEL_RESOLUTIONS = {
    "SD1.5": SD15_RESOLUTIONS,
    "SDXL": SDXL_RESOLUTIONS,
    # Add other models here in the future if needed
}

# Dictionary defining standard aspect ratios commonly used in photography/cinematography.
# Keys are human-readable names (used in the UI dropdown).
# Values are the numerical aspect ratio (width / height).
# Including orientation in the name helps disambiguate (e.g., 2:3 vs 3:2).
ASPECT_RATIOS = {
    "9:16 Portrait (Mobile Video)": 9/16,       # 0.5625
    "2:3 Portrait (35mm Photo)": 2/3, # ~0.6667
    "3:4 Portrait (Classic Monitor/Photo)": 3/4,         # 0.75
    "4:5 Portrait (Large Format Photo)": 4/5,         # 0.8
    "1:1 Square (Instagram/Medium Format)": 1.0,
    "5:4 Landscape (Large Format Photo)": 5/4,         # 1.25
    "4:3 Landscape (Classic Monitor/Photo)": 4/3,         # ~1.3333
    "3:2 Landscape (35mm Photo)": 3/2, # 1.5
    "16:9 Landscape (HD Video/Widescreen)": 16/9, # ~1.7778
    "~2.39:1 Landscape (Anamorphic Cinema)": 2.39, # Approximation for common cinematic wide formats
}

# --- Node Class ---
# Defines the main logic and properties of the ComfyUI node.
class HolafResolutionPreset:
    @classmethod
    def INPUT_TYPES(cls):
        """
        Defines the input fields presented in the ComfyUI node interface.
        'required' inputs must be provided for the node to function.
        """
        return {
            "required": {
                # Dropdown to select the target model type (e.g., SD1.5, SDXL).
                # Populated dynamically from the keys of MODEL_RESOLUTIONS.
                "model_type": (list(MODEL_RESOLUTIONS.keys()),),
                # Dropdown to select the desired aspect ratio.
                # Populated dynamically from the keys of ASPECT_RATIOS.
                "aspect_ratio": (list(ASPECT_RATIOS.keys()),),
            }
            # 'optional' inputs could be added here if needed in the future.
        }

    # Define the data types of the outputs provided by the node.
    RETURN_TYPES = ("INT", "INT")
    # Define the names of the outputs (used for connecting to other nodes).
    RETURN_NAMES = ("width", "height")
    # Specifies the method within this class that executes the node's logic.
    FUNCTION = "get_resolution"
    # Defines the category under which this node will appear in the ComfyUI menu.
    CATEGORY = "Holaf" # Changed from _for_testing

    def get_resolution(self, model_type, aspect_ratio):
        """
        Core logic of the node. Takes the selected model type and aspect ratio
        and returns the width and height of the best matching native resolution.
        """
        # 1. Get the numerical target ratio from the selected aspect ratio name.
        target_ratio = ASPECT_RATIOS[aspect_ratio]
        # 2. Get the list of recommended resolutions for the selected model type.
        available_resolutions = MODEL_RESOLUTIONS[model_type]

        # 3. Determine the desired orientation (portrait, square, landscape)
        #    based on the target aspect ratio.
        is_portrait = target_ratio < 1.0
        is_square = target_ratio == 1.0
        is_landscape = target_ratio > 1.0

        # 4. Filter the available resolutions to only include those matching the
        #    desired orientation. This prevents selecting a portrait resolution
        #    when a landscape ratio was requested, and vice-versa.
        filtered_resolutions = []
        for w, h, r in available_resolutions:
            # Determine orientation of the current resolution being checked
            res_is_portrait = r < 1.0
            res_is_square = r == 1.0
            res_is_landscape = r > 1.0

            # Keep the resolution if its orientation matches the target orientation
            if (is_portrait and res_is_portrait) or \
               (is_square and res_is_square) or \
               (is_landscape and res_is_landscape):
                filtered_resolutions.append((w, h, r))

        # 5. Handle the unlikely case where no resolutions match the orientation.
        #    This might happen if the data is incomplete or inconsistent.
        #    As a fallback, return the first resolution listed for that model type.
        if not filtered_resolutions:
             print(f"[HolafResolutionPreset] Warning: No native resolutions found matching the orientation "
                   f"for {model_type} and {aspect_ratio}. Falling back to the first available resolution.")
             # Use the first resolution from the *unfiltered* list as a fallback
             fallback_res = available_resolutions[0]
             return (fallback_res[0], fallback_res[1])

        # 6. Find the best match among the filtered resolutions.
        #    The best match is the one whose numerical aspect ratio (res[2])
        #    is closest to the target numerical aspect ratio.
        #    The `min` function with a `key` based on the absolute difference achieves this.
        best_match = min(filtered_resolutions, key=lambda res: abs(res[2] - target_ratio))

        # 7. Return the width (best_match[0]) and height (best_match[1])
        #    of the best matching resolution.
        return (best_match[0], best_match[1])

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
