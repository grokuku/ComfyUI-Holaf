# Copyright (C) 2025 Holaf
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

import math
import sys
import random
import torch

# --- Predefined Optimal Resolutions ---
# These are lists of (width, height, aspect_ratio) tuples that are known to
# work well with their respective models, minimizing artifacts.

# Resolutions commonly used or trained for SD 1.5 models.
SD15_RESOLUTIONS = [
    (512, 512, 1.0),
    (768, 512, 1.5),
    (512, 768, 512/768),
]

# Resolutions officially recommended by Stability AI for SDXL 1.0.
SDXL_RESOLUTIONS = [
    (1024, 1024, 1.0),
    (1152, 896, 1152/896),
    (896, 1152, 896/1152),
    (1216, 832, 1216/832),
    (832, 1216, 832/1216),
    (1344, 768, 1344/768),
    (768, 1344, 768/1344),
    (1536, 640, 1536/640),
    (640, 1536, 640/1536),
]

# Recommended resolutions for FLUX, respecting its unique constraints
# (e.g., total pixels ~1-2M, multiples of 8).
FLUX_RESOLUTIONS = [
    (896, 1600, 896/1600),     # 9:16 Portrait
    (1024, 1536, 1024/1536),    # 2:3 Portrait
    (1200, 1600, 1200/1600),    # 3:4 Portrait
    (1024, 1280, 1024/1280),    # 4:5 Portrait
    (1024, 1024, 1.0),         # 1:1 Square
    (1280, 1024, 1280/1024),    # 5:4 Landscape
    (1600, 1200, 1600/1200),    # 4:3 Landscape
    (1536, 1024, 1536/1024),    # 3:2 Landscape
    (1824, 1024, 1824/1024),    # 16:9 Landscape
    (1832, 768, 1832/768),     # ~2.39:1 Landscape
]

# --- Constraints for Dynamically Calculated Resolutions ---
# These parameters are used when no predefined resolution matches the target aspect ratio.
MODEL_MP_RANGES = { # Target total pixel count (Megapixels)
    "SD1.5": (250000, 600000),
    "SDXL": (1000000, 1500000),
    "FLUX": (1000000, 2000000),
}
MODEL_ROUNDING = { # Dimensions must be a multiple of this value.
    "SD1.5": 64,
    "SDXL": 8,
    "FLUX": 8,
}
MODEL_MAX_DIMS = { # The largest recommended side for generation.
    "SD1.5": 768,
    "SDXL": 1536,
    "FLUX": 1832,
}
MODEL_RESOLUTIONS = {
    "SD1.5": SD15_RESOLUTIONS,
    "SDXL": SDXL_RESOLUTIONS,
    "FLUX": FLUX_RESOLUTIONS,
}

# A small tolerance for comparing float aspect ratios.
RATIO_TOLERANCE = sys.float_info.epsilon * 10

# Maps user-friendly names to their float values for the UI dropdown.
ASPECT_RATIOS = {
    "9:16 Portrait (Mobile Video)": 9/16,
    "2:3 Portrait (35mm Photo)": 2/3,
    "3:4 Portrait (Classic Monitor-Photo)": 3/4,
    "4:5 Portrait (Large Format Photo)": 4/5,
    "1:1 Square (Instagram-Medium Format)": 1.0,
    "5:4 Landscape (Large Format Photo)": 5/4,
    "4:3 Landscape (Classic Monitor-Photo)": 4/3,
    "3:2 Landscape (35mm Photo)": 3/2,
    "16:9 Landscape (HD Video-Widescreen)": 16/9,
    "~2.39:1 Landscape (Anamorphic Cinema)": 2.39,
}


class HolafResolutionPreset:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_type": (list(MODEL_RESOLUTIONS.keys()),),
                "aspect_ratio": (["Random"] + list(ASPECT_RATIOS.keys()),),
                "use_image_ratio": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                 "image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("width", "height")
    FUNCTION = "get_resolution"
    CATEGORY = "Holaf"

    def IS_CHANGED(self, model_type, aspect_ratio, use_image_ratio, image=None):
        """
        Forces the node to re-execute under specific conditions. This is crucial for
        the "Random" option to ensure a new resolution is picked on each run.
        It also re-runs if the input image's shape changes when `use_image_ratio` is active.
        """
        if aspect_ratio == "Random":
            return random.random()

        image_hash = "no_image"
        if use_image_ratio and image is not None and isinstance(image, torch.Tensor):
            image_hash = hash(image.shape)

        return f"{model_type}-{aspect_ratio}-{use_image_ratio}-{image_hash}"

    def _round_to_multiple(self, value, multiple):
        """Helper function to round a value to the nearest specified multiple."""
        if multiple == 0:
            return max(1, round(value))
        return max(multiple, round(value / multiple) * multiple)

    def get_resolution(self, model_type, aspect_ratio, use_image_ratio, image=None):
        """
        Determines and returns an optimal width and height based on user inputs.
        """
        target_ratio = None
        
        # 1. Determine the target aspect ratio. Priority is given to the input image.
        if use_image_ratio and image is not None and isinstance(image, torch.Tensor) and image.ndim == 4:
            img_height, img_width = image.shape[1], image.shape[2]
            if img_height > 0 and img_width > 0:
                target_ratio = img_width / img_height

        # If not using image ratio, use the dropdown selection.
        if target_ratio is None:
            if aspect_ratio == "Random":
                selected_name = random.choice(list(ASPECT_RATIOS.keys()))
                target_ratio = ASPECT_RATIOS[selected_name]
            else:
                target_ratio = ASPECT_RATIOS.get(aspect_ratio, 1.0)
        
        # 2. Get the list of predefined resolutions for the selected model.
        available_resolutions = MODEL_RESOLUTIONS[model_type]

        # 3. Try to find a predefined resolution that perfectly matches the target ratio.
        # This is the ideal case.
        for w, h, r in available_resolutions:
            if abs(r - target_ratio) < RATIO_TOLERANCE:
                print(f"[HolafResolutionPreset] Found exact predefined match: {w}x{h}")
                return (w, h)

        # 4. If no exact match is found, calculate a new resolution from scratch.
        print(f"[HolafResolutionPreset] No exact match for ratio {target_ratio:.4f}. Calculating new resolution...")
        
        # Get the calculation constraints for the selected model.
        max_dim = MODEL_MAX_DIMS[model_type]
        min_pixels, max_pixels = MODEL_MP_RANGES[model_type]
        rounding = MODEL_ROUNDING[model_type]

        # Calculate initial dimensions based on the model's max dimension and target ratio.
        is_landscape_or_square = target_ratio >= 1.0
        if is_landscape_or_square:
            width_initial, height_initial = max_dim, max_dim / target_ratio
        else: # Portrait
            height_initial, width_initial = max_dim, max_dim * target_ratio

        # Scale the dimensions to fit within the model's recommended megapixel range.
        current_pixels = width_initial * height_initial
        if current_pixels > 0:
            scale_factor = 1.0
            if current_pixels < min_pixels:
                scale_factor = math.sqrt(min_pixels / current_pixels)
            elif current_pixels > max_pixels:
                scale_factor = math.sqrt(max_pixels / current_pixels)
            
            width_adjusted = width_initial * scale_factor
            height_adjusted = height_initial * scale_factor
        else:
            width_adjusted, height_adjusted = 512, 512 # Fallback

        # Round the final dimensions to the required multiple (e.g., 64 for SD1.5).
        final_width = self._round_to_multiple(width_adjusted, rounding)
        final_height = self._round_to_multiple(height_adjusted, rounding)

        print(f"[HolafResolutionPreset] Calculated Resolution: W={final_width}, H={final_height}")
        return (final_width, final_height)