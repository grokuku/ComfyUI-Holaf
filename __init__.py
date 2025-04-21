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
#   `NODE_DISPLAY_NAME_MAPPINGS`) to be exported when the package is imported.
#   This is standard Python practice and ensures ComfyUI can access these essential variables.
# - Initialization Feedback: Includes a print statement to the console upon successful
#   loading, providing visual confirmation that the custom node package has been
#   recognized and initialized by ComfyUI.
# === End Documentation ===
# Removed HolafGlitchImageNode

# Import classes from the nodes directory
# Removed import for HolafHello
from .nodes.holaf_neurogrid_overload import HolafNeurogridOverload
from .nodes.holaf_tile_calculator import HolafTileCalculator
from .nodes.holaf_slice_calculator import HolafSliceCalculator # Added import
from .nodes.holaf_save_image import HolafSaveImage # Added import
from .nodes.holaf_tiled_ksampler import HolafTiledKSampler # Renamed import
from .nodes.holaf_ksampler import HolafKSampler # Added import for the new KSampler
from .nodes.holaf_image_comparer import HolafImageComparer # Updated import path and class name
from .nodes.holaf_upscale_image import UpscaleImageHolaf # Added import for Upscale node
from .nodes.holaf_overlay import HolafOverlayNode # Added import for Overlay node
from .nodes.holaf_resolution_preset import HolafResolutionPreset # Added import for Resolution Preset node
from .nodes.HolafBenchmarkRunner import HolafBenchmarkRunner # Added import for Benchmark Runner node
from .nodes.HolafBenchmarkPlotter import HolafBenchmarkPlotter # Added import for Benchmark Plotter node
from .nodes.HolafBenchmarkLoader import HolafBenchmarkLoader # Added import for Benchmark Loader node
from .nodes.holaf_instagram_resize import HolafInstagramResize
# Removed import for HolafToText
# Removed import for HolafImageCompare
# Removed import for HolafAnyToText

# Define node mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    # Removed mapping for HolafHello
    "HolafNeurogridOverload": HolafNeurogridOverload,
    "HolafTileCalculator": HolafTileCalculator,
    "HolafSliceCalculator": HolafSliceCalculator, # Added mapping
    "HolafSaveImage": HolafSaveImage, # Added mapping
    "HolafTiledKSampler": HolafTiledKSampler, # Renamed mapping
    "HolafKSampler": HolafKSampler, # Added mapping for the new KSampler
    'HolafImageComparer': HolafImageComparer, # Use Class Name as key
    "UpscaleImageHolaf": UpscaleImageHolaf, # Added mapping for Upscale node
    "HolafOverlayNode": HolafOverlayNode, # Added mapping for Overlay node
    "HolafResolutionPreset": HolafResolutionPreset, # Added mapping for Resolution Preset node
    "HolafBenchmarkRunner": HolafBenchmarkRunner, # Added mapping for Benchmark Runner node
    "HolafBenchmarkPlotter": HolafBenchmarkPlotter, # Added mapping for Benchmark Plotter node
    "HolafBenchmarkLoader": HolafBenchmarkLoader, # Added mapping for Benchmark Loader node
    "HolafInstagramResize": HolafInstagramResize,
    # Removed mapping for HolafToText
    # Removed mapping for HolafImageCompare
    # Removed mapping for HolafAnyToText
}

# Define display name mappings
NODE_DISPLAY_NAME_MAPPINGS = {
    # Removed display name for HolafHello
    "HolafNeurogridOverload": "Neurogrid Overload (Holaf)",
    "HolafTileCalculator": "Tile Calculator (Holaf)",
    "HolafSliceCalculator": "Slice Calculator (Holaf)",
    "HolafSaveImage": "Save Image (Holaf)", # Added display name
    "HolafTiledKSampler": "Tiled KSampler (Holaf)", # Renamed key
    "HolafKSampler": "KSampler (Holaf)", # Added display name for the new KSampler
    'HolafImageComparer': "Image Comparer (Holaf)", # Updated key and display name
    "UpscaleImageHolaf": "Upscale (Holaf)", # Added display name for Upscale node
    "HolafOverlayNode": "Overlay (Holaf)", # Added display name for Overlay node
    "HolafResolutionPreset": "Resolution Preset (Holaf)", # Added display name for Resolution Preset node
    "HolafBenchmarkRunner": "Benchmark Runner (Holaf)", # Added display name for Benchmark Runner node
    "HolafBenchmarkPlotter": "Benchmark Plotter (Holaf)", # Added display name for Benchmark Plotter node
    "HolafBenchmarkLoader": "Benchmark Loader (Holaf)", # Added display name for Benchmark Loader node
    # Removed display name for HolafToText
    # Removed display name for HolafImageCompare
    # Removed display name for HolafAnyToText
    "HolafInstagramResize": "Instagram Resize (Holaf)",
}

# Define the web directory for JavaScript files
WEB_DIRECTORY = "./js"

# Indicate successful loading
print("✅ Holaf Nodes Root initialized")

# Export mappings for ComfyUI
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
