# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-01
#
# Purpose:
# This __init__.py file serves as the main entry point for the 'ComfyUI-Holaf'
# custom node package. It is responsible for making the custom nodes defined
# within this package discoverable and usable by the ComfyUI application.
#
# Design Choices & Rationale:
# - Centralized Registration: Follows the standard ComfyUI pattern for custom
#   node packages. ComfyUI looks for this file to understand what nodes the
#   package provides.
# - Modular Imports: Imports individual node classes (e.g., HolafTileCalculator,
#   HolafSaveImage) from their respective files within the `./nodes/` subdirectory.
#   This keeps the node implementations organized in separate files.
# - NODE_CLASS_MAPPINGS: This dictionary is crucial for ComfyUI. It maps a unique
#   internal string identifier (typically the class name) for each node to the
#   actual Python class that implements the node's logic. ComfyUI uses this map
#   to instantiate the correct node object when loading or running a workflow.
# - NODE_DISPLAY_NAME_MAPPINGS: This dictionary maps the same internal string
#   identifiers to user-friendly names that appear in the ComfyUI "Add Node" menu.
#   This allows for more readable or descriptive names than the raw class names.
# - WEB_DIRECTORY: Specifies the relative path to the directory containing
#   associated web assets (JavaScript files in this case) needed for the frontend
#   components of certain custom nodes (like HolafImageComparer). ComfyUI serves
#   files from this directory.
# - __all__ Export: Explicitly lists the mapping dictionaries (`NODE_CLASS_MAPPINGS`,
#   `NODE_DISPLAY_NAME_MAPPINGS`, `WEB_DIRECTORY`) to be exported when the package is imported.
#   This is standard Python practice and ensures ComfyUI can access these essential variables.
# - Initialization Feedback: Includes a print statement to the console upon successful
#   loading, providing visual confirmation that the custom node package has been
#   recognized and initialized by ComfyUI.
# === End Documentation ===

# Import classes from the nodes directory
from .nodes.holaf_neurogrid_overload import HolafNeurogridOverload
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
# from .nodes.holaf_interactive_image_editor import HolafInteractiveImageEditor # <-- IMPORTATION SUPPRIMÉE
from .nodes.holaf_color_matcher import HolafColorMatcher

# Define node mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "HolafNeurogridOverload": HolafNeurogridOverload,
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
    # "HolafInteractiveImageEditor": HolafInteractiveImageEditor, # <-- MAPPING SUPPRIMÉ
    "HolafColorMatcher": HolafColorMatcher,
}

# Define display name mappings
NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafNeurogridOverload": "Neurogrid Overload (Holaf)",
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
    # "HolafInteractiveImageEditor": "Interactive Image Editor (Holaf)", # <-- NOM D'AFFICHAGE SUPPRIMÉ
    "HolafColorMatcher": "Color Matcher (Holaf)",
}

# Define the web directory for JavaScript files
# This tells ComfyUI where to find your JS files.
# The path is relative to this __init__.py file.
WEB_DIRECTORY = "./js"

# Indicate successful loading
print("✅ Holaf Custom Nodes initialized") # <-- MESSAGE D'INITIALISATION NETTOYÉ

# Export mappings for ComfyUI
# It's good practice to also export WEB_DIRECTORY if your nodes use it.
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']