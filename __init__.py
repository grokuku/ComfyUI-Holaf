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
from .nodes.holaf_save_media import HolafSaveMedia
from .nodes.holaf_tiled_ksampler import HolafTiledKSampler

from .nodes.holaf_ksampler import HolafKSampler
from .nodes.holaf_image_comparer import HolafImageComparer
from .nodes.holaf_upscale_image import UpscaleImageHolaf
from .nodes.holaf_overlay import HolafOverlayNode
from .nodes.holaf_resolution_preset import HolafResolutionPreset
from .nodes.holaf_instagram_resize import HolafInstagramResize
from .nodes.holaf_lut_generator import HolafLutGenerator
from .nodes.holaf_lut_saver import HolafLutSaver
from .nodes.holaf_mask_to_boolean import HolafMaskToBoolean
from .nodes.holaf_bypasser import HolafBypasser
from .nodes.holaf_group_bypasser import HolafGroupBypasser
from .nodes.holaf_remote import HolafRemote
from .nodes.holaf_load_image_video import HolafLoadImageVideo
from .nodes.holaf_image_batch_slice import HolafImageBatchSlice
from .nodes.holaf_video_preview import HolafVideoPreview
from .nodes.holaf_text_box import HolafTextBox
from .nodes.holaf_to_text import HolafToText
from .nodes.holaf_image_adjustment import HolafImageAdjustment

# New Dynamic Bundle Nodes
from .nodes.holaf_bundle_creator import HolafBundleCreator
from .nodes.holaf_bundle_extractor import HolafBundleExtractor

# New Auto Select Node
from .nodes.holaf_auto_select_x2 import HolafAutoSelectX2

# New Remote Selector Node
from .nodes.holaf_remote_selector import HolafRemoteSelector

# Nucleus-Image node (optional — requires diffusers >= 0.38)
# Protected import: if diffusers is not installed or too old, the node is
# simply skipped so the rest of the pack keeps working.
try:
    from .nodes.holaf_nucleus_image import HolafNucleusImage
    _nucleus_image_available = True
except ImportError:
    _nucleus_image_available = False
    print("⚠️  Holaf Nucleus-Image node skipped: diffusers not installed or too old.")
    print("   Install with: pip install git+https://github.com/huggingface/diffusers")


# Maps internal class names to the node's implementation.
NODE_CLASS_MAPPINGS = {
    "HolafSaveMedia": HolafSaveMedia,
    "HolafTiledKSampler": HolafTiledKSampler,

    "HolafKSampler": HolafKSampler,
    'HolafImageComparer': HolafImageComparer,
    "UpscaleImageHolaf": UpscaleImageHolaf,
    "HolafOverlayNode": HolafOverlayNode,
    "HolafResolutionPreset": HolafResolutionPreset,
    "HolafInstagramResize": HolafInstagramResize,
    "HolafLutGenerator": HolafLutGenerator,
    "HolafLutSaver": HolafLutSaver,
    "HolafMaskToBoolean": HolafMaskToBoolean,
    "HolafBypasser": HolafBypasser,
    "HolafGroupBypasser": HolafGroupBypasser,
    "HolafRemote": HolafRemote,
    "HolafLoadImageVideo": HolafLoadImageVideo,
    "HolafImageBatchSlice": HolafImageBatchSlice,
    "HolafVideoPreview": HolafVideoPreview,
    "HolafTextBox": HolafTextBox,
    "HolafToText": HolafToText,
    "HolafImageAdjustment": HolafImageAdjustment,

    "HolafBundleCreator": HolafBundleCreator,
    "HolafBundleExtractor": HolafBundleExtractor,
    "HolafAutoSelectX2": HolafAutoSelectX2,
    "HolafRemoteSelector": HolafRemoteSelector,
}

# Maps internal class names to a user-friendly display name for the ComfyUI menu.
NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafSaveMedia": "Save Media (Holaf)",
    "HolafTiledKSampler": "Tiled KSampler (Holaf)",

    "HolafKSampler": "KSampler (Holaf)",
    'HolafImageComparer': "Image Comparer (Holaf)",
    "UpscaleImageHolaf": "Upscale (Holaf)",
    "HolafOverlayNode": "Overlay (Holaf)",
    "HolafResolutionPreset": "Resolution Preset (Holaf)",
    "HolafInstagramResize": "Instagram Resize (Holaf)",
    "HolafLutGenerator": "LUT Generator (Holaf)",
    "HolafLutSaver": "LUT Saver (Holaf)",
    "HolafMaskToBoolean": "Mask to Boolean (Holaf)",
    "HolafBypasser": "Bypasser (Holaf)",
    "HolafGroupBypasser": "Group Bypasser (Holaf)",
    "HolafRemote": "Remote (Holaf)",
    "HolafLoadImageVideo": "Load Image/Video (Holaf)",
    "HolafImageBatchSlice": "Image Batch Slice (Holaf)",
    "HolafVideoPreview": "Video Preview (Holaf)",
    "HolafTextBox": "Text Box (Holaf)",
    "HolafToText": "To Text (Holaf)",
    "HolafImageAdjustment": "Image Adjustment (Holaf)",

    "HolafBundleCreator": "Bundle Creator (Holaf)",
    "HolafBundleExtractor": "Bundle Extractor (Holaf)",
    "HolafAutoSelectX2": "Auto Select x2 (Holaf)",
    "HolafRemoteSelector": "Remote Selector (Holaf)",
}

# Conditionally register the Nucleus-Image node
if _nucleus_image_available:
    NODE_CLASS_MAPPINGS["HolafNucleusImage"] = HolafNucleusImage
    NODE_DISPLAY_NAME_MAPPINGS["HolafNucleusImage"] = "Nucleus-Image (Holaf)"

# The WEB_DIRECTORY tells ComfyUI where to look for JavaScript files that correspond to the Python nodes.
WEB_DIRECTORY = "./js"

# Indicate successful loading in the console.
_nucleus_status = "✅ Nucleus-Image node loaded." if _nucleus_image_available else "⚠️  Nucleus-Image node skipped (missing deps)."
print(f"✅ Holaf Custom Nodes initialized  {_nucleus_status}")

# Export mappings for ComfyUI to use.
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
