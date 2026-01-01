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

# Master dictionary defining a single, optimal resolution for each
# model and aspect ratio combination. This enforces deterministic behavior.
MASTER_RESOLUTIONS = {
    "SD1.5": {
        "9:16 Portrait (Mobile Video)": (512, 912),
        "2:3 Portrait (35mm Photo)": (512, 768),
        "3:4 Portrait (Classic Monitor-Photo)": (576, 768),
        "4:5 Portrait (Large Format Photo)": (512, 640),
        "1:1 Square (Instagram-Medium Format)": (512, 512),
        "5:4 Landscape (Large Format Photo)": (640, 512),
        "4:3 Landscape (Classic Monitor-Photo)": (768, 576),
        "3:2 Landscape (35mm Photo)": (768, 512),
        "16:9 Landscape (HD Video-Widescreen)": (912, 512),
        "~2.39:1 Landscape (Anamorphic Cinema)": (1024, 432),
    },
    "SDXL": {
        "9:16 Portrait (Mobile Video)": (768, 1344),
        "2:3 Portrait (35mm Photo)": (832, 1216),
        "3:4 Portrait (Classic Monitor-Photo)": (896, 1152),
        "4:5 Portrait (Large Format Photo)": (896, 1120),
        "1:1 Square (Instagram-Medium Format)": (1024, 1024),
        "5:4 Landscape (Large Format Photo)": (1120, 896),
        "4:3 Landscape (Classic Monitor-Photo)": (1152, 864),
        "3:2 Landscape (35mm Photo)": (1216, 832),
        "16:9 Landscape (HD Video-Widescreen)": (1344, 768),
        "~2.39:1 Landscape (Anamorphic Cinema)": (1536, 640),
    },
    "FLUX": {
        "9:16 Portrait (Mobile Video)": (896, 1600),
        "2:3 Portrait (35mm Photo)": (1024, 1536),
        "3:4 Portrait (Classic Monitor-Photo)": (1200, 1600),
        "4:5 Portrait (Large Format Photo)": (1024, 1280),
        "1:1 Square (Instagram-Medium Format)": (1024, 1024),
        "5:4 Landscape (Large Format Photo)": (1280, 1024),
        "4:3 Landscape (Classic Monitor-Photo)": (1600, 1200),
        "3:2 Landscape (35mm Photo)": (1536, 1024),
        "16:9 Landscape (HD Video-Widescreen)": (1824, 1024),
        "~2.39:1 Landscape (Anamorphic Cinema)": (1832, 768),
    },
    "Qwen-Image": {
        "9:16 Portrait (Mobile Video)": (928, 1664),
        "2:3 Portrait (35mm Photo)": (1056, 1584),
        "3:4 Portrait (Classic Monitor-Photo)": (1104, 1472),
        "4:5 Portrait (Large Format Photo)": (1328, 1660),
        "1:1 Square (Instagram-Medium Format)": (1328, 1328),
        "5:4 Landscape (Large Format Photo)": (1660, 1328),
        "4:3 Landscape (Classic Monitor-Photo)": (1472, 1104),
        "3:2 Landscape (35mm Photo)": (1584, 1056),
        "16:9 Landscape (HD Video-Widescreen)": (1664, 928),
        "~2.39:1 Landscape (Anamorphic Cinema)": (1792, 752),
    },
    "Qwen-Edit": {
        "9:16 Portrait (Mobile Video)": (928, 1664),
        "2:3 Portrait (35mm Photo)": (1056, 1584),
        "3:4 Portrait (Classic Monitor-Photo)": (1104, 1472),
        "4:5 Portrait (Large Format Photo)": (1328, 1660),
        "1:1 Square (Instagram-Medium Format)": (1328, 1328),
        "5:4 Landscape (Large Format Photo)": (1660, 1328),
        "4:3 Landscape (Classic Monitor-Photo)": (1472, 1104),
        "3:2 Landscape (35mm Photo)": (1584, 1056),
        "16:9 Landscape (HD Video-Widescreen)": (1664, 928),
        "~2.39:1 Landscape (Anamorphic Cinema)": (1792, 752),
    },
    "Z-Image": {
        "9:16 Portrait (Mobile Video)": (768, 1344),
        "2:3 Portrait (35mm Photo)": (832, 1216),
        "3:4 Portrait (Classic Monitor-Photo)": (896, 1152),
        "4:5 Portrait (Large Format Photo)": (896, 1120),
        "1:1 Square (Instagram-Medium Format)": (1024, 1024),
        "5:4 Landscape (Large Format Photo)": (1120, 896),
        "4:3 Landscape (Classic Monitor-Photo)": (1152, 864),
        "3:2 Landscape (35mm Photo)": (1216, 832),
        "16:9 Landscape (HD Video-Widescreen)": (1344, 768),
        "~2.39:1 Landscape (Anamorphic Cinema)": (1536, 640),
    },
}


class HolafResolutionPreset:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model_type": (list(MASTER_RESOLUTIONS.keys()),),
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
        if aspect_ratio == "Random":
            return random.random()

        image_hash = "no_image"
        if use_image_ratio and image is not None and isinstance(image, torch.Tensor):
            image_hash = hash(image.shape)

        return f"{model_type}-{aspect_ratio}-{use_image_ratio}-{image_hash}"

    def get_resolution(self, model_type, aspect_ratio, use_image_ratio, image=None):
        target_ratio_name = aspect_ratio

        # If using image ratio, find the closest matching ratio name from our list
        if use_image_ratio and image is not None and isinstance(image, torch.Tensor) and image.ndim == 4:
            img_height, img_width = image.shape[1], image.shape[2]
            if img_height > 0 and img_width > 0:
                image_ratio = img_width / img_height
                # Find the aspect ratio name in ASPECT_RATIOS that is closest to image_ratio
                closest_ratio_name = min(ASPECT_RATIOS.keys(), key=lambda name: abs(ASPECT_RATIOS[name] - image_ratio))
                target_ratio_name = closest_ratio_name
                print(f"[HolafResolutionPreset] Detected image ratio ~{image_ratio:.2f}. Matched to '{target_ratio_name}'.")

        # Handle random selection
        if target_ratio_name == "Random":
            target_ratio_name = random.choice(list(ASPECT_RATIOS.keys()))

        # The core of the new logic: a direct lookup.
        # Fallback to 1:1 if the ratio name is somehow invalid.
        if target_ratio_name not in MASTER_RESOLUTIONS[model_type]:
            print(f"[HolafResolutionPreset] Warning: Ratio '{target_ratio_name}' not found for model '{model_type}'. Defaulting to 1:1.")
            target_ratio_name = "1:1 Square (Instagram-Medium Format)"

        width, height = MASTER_RESOLUTIONS[model_type][target_ratio_name]

        print(f"[HolafResolutionPreset] Selected: {model_type} @ {target_ratio_name}. Resolution: {width}x{height}")
        return (width, height)