"""
This file is the main entry point for the ComfyUI-Holaf custom node package.
It is responsible for discovering, importing, and registering all the custom nodes
and their associated web assets (JavaScript files) with ComfyUI.
"""

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
from .nodes.holaf_image_comparer import HolafImageComparer
from .nodes.holaf_upscale_image import UpscaleImageHolaf
from .nodes.holaf_overlay import HolafOverlayNode
from .nodes.holaf_resolution_preset import HolafResolutionPreset
from .nodes.HolafBenchmarkRunner import HolafBenchmarkRunner
from .nodes.HolafBenchmarkPlotter import HolafBenchmarkPlotter
from .nodes.HolafBenchmarkLoader import HolafBenchmarkLoader
from .nodes.holaf_instagram_resize import HolafInstagramResize
from .nodes.holaf_color_matcher import HolafColorMatcher
from .nodes.holaf_lut_generator import HolafLutGenerator
from .nodes.holaf_lut_applier import HolafLutApplier
from .nodes.holaf_lut_loader import HolafLutLoader
from .nodes.holaf_lut_saver import HolafLutSaver
from .nodes.holaf_interactive_image_editor import HolafInteractiveImageEditor
from .nodes.holaf_mask_to_boolean import HolafMaskToBoolean


# Maps internal class names to the node's implementation.
# ComfyUI uses this to instantiate the correct node class.
NODE_CLASS_MAPPINGS = {
    "HolafTileCalculator": HolafTileCalculator,
    "HolafSliceCalculator": HolafSliceCalculator,
    "HolafSaveImage": HolafSaveImage,
    "HolafTiledKSampler": HolafTiledKSampler,
    "HolafKSampler": HolafKSampler,
    'HolafImageComparer': HolafImageComparer,
    "UpscaleImageHolaf": UpscaleImageHolaf,
    "HolafOverlayNode": HolafOverlayNode,
    "HolafResolutionPreset": HolafResolutionPreset,
    "HolafBenchmarkRunner": HolafBenchmarkRunner,
    "HolafBenchmarkPlotter": HolafBenchmarkPlotter,
    "HolafBenchmarkLoader": HolafBenchmarkLoader,
    "HolafInstagramResize": HolafInstagramResize,
    "HolafColorMatcher": HolafColorMatcher,
    "HolafLutGenerator": HolafLutGenerator,
    "HolafLutApplier": HolafLutApplier,
    "HolafLutLoader": HolafLutLoader,
    "HolafLutSaver": HolafLutSaver,
    "HolafInteractiveImageEditor": HolafInteractiveImageEditor,
    "HolafMaskToBoolean": HolafMaskToBoolean,
}

# Maps internal class names to a user-friendly display name for the ComfyUI menu.
NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafTileCalculator": "Tile Calculator (Holaf)",
    "HolafSliceCalculator": "Slice Calculator (Holaf)",
    "HolafSaveImage": "Save Image (Holaf)",
    "HolafTiledKSampler": "Tiled KSampler (Holaf)",
    "HolafKSampler": "KSampler (Holaf)",
    'HolafImageComparer': "Image Comparer (Holaf)",
    "UpscaleImageHolaf": "Upscale (Holaf)",
    "HolafOverlayNode": "Overlay (Holaf)",
    "HolafResolutionPreset": "Resolution Preset (Holaf)",
    "HolafBenchmarkRunner": "Benchmark Runner (Holaf)",
    "HolafBenchmarkPlotter": "Benchmark Plotter (Holaf)",
    "HolafBenchmarkLoader": "Benchmark Loader (Holaf)",
    "HolafInstagramResize": "Instagram Resize (Holaf)",
    "HolafColorMatcher": "Color Matcher (Holaf)",
    "HolafLutGenerator": "LUT Generator (Holaf)",
    "HolafLutApplier": "LUT Applier (Holaf)",
    "HolafLutLoader": "LUT Loader (Holaf)",
    "HolafLutSaver": "LUT Saver (Holaf)",
    "HolafInteractiveImageEditor": "Interactive Image Editor (Holaf)",
    "HolafMaskToBoolean": "Mask to Boolean (Holaf)",
}

# --- Dynamic and Versioned JavaScript Loading ---

# Get the absolute path to the 'js' directory for this custom node.
js_web_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "js")

# Make the 'js' directory accessible to the ComfyUI web server under the '/holaf' path.
server.PromptServer.instance.app.router.add_static("/holaf", js_web_path)

# <--- MODIFICATION --->
# The entire block for dynamic JS loading with hashing and the `add_js_file` loop has been removed.
# We will now rely on the `WEB_DIRECTORY` variable below, which is the standard and correct way.
# ComfyUI will automatically look in the specified `WEB_DIRECTORY` for JS files
# that match the Python node file names (e.g., holaf_image_comparer.py -> holaf_image_comparer.js).
# <--- FIN MODIFICATION --->

# The WEB_DIRECTORY tells ComfyUI where to look for JavaScript files that correspond to the Python nodes.
WEB_DIRECTORY = "./js"

# Indicate successful loading in the console.
print("✅ Holaf Custom Nodes initialized")

# Export mappings for ComfyUI to use.
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']