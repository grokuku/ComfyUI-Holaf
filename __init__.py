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
from .nodes.holaf_image_comparer import HolafImageComparer
from .nodes.holaf_upscale_image import UpscaleImageHolaf
from .nodes.holaf_overlay import HolafOverlayNode
from .nodes.holaf_resolution_preset import HolafResolutionPreset
from .nodes.HolafBenchmarkRunner import HolafBenchmarkRunner
from .nodes.HolafBenchmarkPlotter import HolafBenchmarkPlotter
from .nodes.HolafBenchmarkLoader import HolafBenchmarkLoader
from .nodes.holaf_instagram_resize import HolafInstagramResize
from .nodes.holaf_lut_generator import HolafLutGenerator
from .nodes.holaf_lut_saver import HolafLutSaver
from .nodes.holaf_mask_to_boolean import HolafMaskToBoolean
from .nodes.holaf_ratio_calculator import HolafRatioCalculator
from .nodes.holaf_regional_prompter import HolafRegionalPrompter
from .nodes.holaf_regional_sampler import HolafRegionalSampler
# Imports pour l'orchestrateur
from .nodes.holaf_orchestrator_config import HolafOrchestratorConfig
from .nodes.HolafInternalSampler import HolafInternalSampler


# Maps internal class names to the node's implementation.
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
    "HolafLutGenerator": HolafLutGenerator,
    "HolafLutSaver": HolafLutSaver,
    "HolafMaskToBoolean": HolafMaskToBoolean,
    "HolafRatioCalculator": HolafRatioCalculator,
    "HolafRegionalPrompter": HolafRegionalPrompter,
    "HolafRegionalSampler": HolafRegionalSampler,
    # Mappings pour l'orchestrateur
    "HolafOrchestratorConfig": HolafOrchestratorConfig,
    "HolafInternalSampler": HolafInternalSampler,
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
    "HolafLutGenerator": "LUT Generator (Holaf)",
    "HolafLutSaver": "LUT Saver (Holaf)",
    "HolafMaskToBoolean": "Mask to Boolean (Holaf)",
    "HolafRatioCalculator": "Ratio Calculator (Holaf)",
    "HolafRegionalPrompter": "Regional Prompter (Holaf)",
    "HolafRegionalSampler": "Regional Sampler (Holaf)",
    # Noms d'affichage pour l'orchestrateur
    "HolafOrchestratorConfig": "Orchestrator Config (Holaf)",
    "HolafInternalSampler": "Internal Sampler (Holaf)",
}

# The WEB_DIRECTORY tells ComfyUI where to look for JavaScript files that correspond to the Python nodes.
WEB_DIRECTORY = "./js"

# Indicate successful loading in the console.
print("✅ Holaf Custom Nodes initialized")

# Export mappings for ComfyUI to use.
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']