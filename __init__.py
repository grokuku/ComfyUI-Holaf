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

import server
import os
import sys
import hashlib

# Node class imports
from .nodes.holaf_tile_calculator import HolafTileCalculator
from .nodes.holaf_slice_calculator import HolafSliceCalculator
from .nodes.holaf_save_image import HolafSaveImage
from .nodes.holaf_tiled_ksampler import HolafTiledKSampler
from .nodes.holaf_ksampler import HolafKSampler
# <--- RESTAURATION --->
from .nodes.holaf_image_comparer import HolafImageComparer
# <--- FIN RESTAURATION --->
from .nodes.holaf_upscale_image import UpscaleImageHolaf
from .nodes.holaf_overlay import HolafOverlayNode
from .nodes.holaf_resolution_preset import HolafResolutionPreset
from .nodes.HolafBenchmarkRunner import HolafBenchmarkRunner
from .nodes.HolafBenchmarkPlotter import HolafBenchmarkPlotter
from .nodes.HolafBenchmarkLoader import HolafBenchmarkLoader
from .nodes.holaf_instagram_resize import HolafInstagramResize
from .nodes.holaf_lut_generator import HolafLutGenerator
from .nodes.holaf_lut_applier import HolafLutApplier
from .nodes.holaf_lut_loader import HolafLutLoader
from .nodes.holaf_lut_saver import HolafLutSaver
from .nodes.holaf_mask_to_boolean import HolafMaskToBoolean


# Maps internal class names to the node's implementation.
# ComfyUI uses this to instantiate the correct node class.
NODE_CLASS_MAPPINGS = {
    "HolafTileCalculator": HolafTileCalculator,
    "HolafSliceCalculator": HolafSliceCalculator,
    "HolafSaveImage": HolafSaveImage,
    "HolafTiledKSampler": HolafTiledKSampler,
    "HolafKSampler": HolafKSampler,
    # <--- RESTAURATION --->
    'HolafImageComparer': HolafImageComparer,
    # <--- FIN RESTAURATION --->
    "UpscaleImageHolaf": UpscaleImageHolaf,
    "HolafOverlayNode": HolafOverlayNode,
    "HolafResolutionPreset": HolafResolutionPreset,
    "HolafBenchmarkRunner": HolafBenchmarkRunner,
    "HolafBenchmarkPlotter": HolafBenchmarkPlotter,
    "HolafBenchmarkLoader": HolafBenchmarkLoader,
    "HolafInstagramResize": HolafInstagramResize,
    "HolafLutGenerator": HolafLutGenerator,
    "HolafLutApplier": HolafLutApplier,
    "HolafLutLoader": HolafLutLoader,
    "HolafLutSaver": HolafLutSaver,
    "HolafMaskToBoolean": HolafMaskToBoolean,
}

# Maps internal class names to a user-friendly display name for the ComfyUI menu.
NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafTileCalculator": "Tile Calculator (Holaf)",
    "HolafSliceCalculator": "Slice Calculator (Holaf)",
    "HolafSaveImage": "Save Image (Holaf)",
    "HolafTiledKSampler": "Tiled KSampler (Holaf)",
    "HolafKSampler": "KSampler (Holaf)",
    # <--- RESTAURATION --->
    'HolafImageComparer': "Image Comparer (Holaf)",
    # <--- FIN RESTAURATION --->
    "UpscaleImageHolaf": "Upscale (Holaf)",
    "HolafOverlayNode": "Overlay (Holaf)",
    "HolafResolutionPreset": "Resolution Preset (Holaf)",
    "HolafBenchmarkRunner": "Benchmark Runner (Holaf)",
    "HolafBenchmarkPlotter": "Benchmark Plotter (Holaf)",
    "HolafBenchmarkLoader": "Benchmark Loader (Holaf)",
    "HolafInstagramResize": "Instagram Resize (Holaf)",
    "HolafLutGenerator": "LUT Generator (Holaf)",
    "HolafLutApplier": "LUT Applier (Holaf)",
    "HolafLutLoader": "LUT Loader (Holaf)",
    "HolafLutSaver": "LUT Saver (Holaf)",
    "HolafMaskToBoolean": "Mask to Boolean (Holaf)",
}

# The WEB_DIRECTORY tells ComfyUI where to look for JavaScript files that correspond to the Python nodes.
WEB_DIRECTORY = "./js"

# Indicate successful loading in the console.
print("✅ Holaf Custom Nodes initialized")

# Export mappings for ComfyUI to use.
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']