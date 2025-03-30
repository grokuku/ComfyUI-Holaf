# Import classes from the nodes directory
# Removed import for HolafHello
from .nodes.holaf_neurogrid_overload import HolafNeurogridOverload
from .nodes.holaf_tile_calculator import HolafTileCalculator
from .nodes.holaf_slice_calculator import HolafSliceCalculator # Added import
from .nodes.holaf_save_image import HolafSaveImage # Added import
from .nodes.holaf_tiled_ksampler import HolafTiledKSampler # Renamed import
from .nodes.holaf_image_comparer import HolafImageComparer # Updated import path and class name
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
    'test comparer': HolafImageComparer, # Updated mapping key and value
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
    'test comparer': "Test Comparer (Holaf)", # Updated display name mapping
    # Removed display name for HolafImageCompare
    # Removed display name for HolafAnyToText
}

# Define the web directory for JavaScript files
WEB_DIRECTORY = "./js"

# Indicate successful loading
print("✅ Holaf Nodes Root initialized")

# Export mappings for ComfyUI
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']
