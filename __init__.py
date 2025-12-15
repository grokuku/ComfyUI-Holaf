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
from .nodes.holaf_save_image import HolafSaveImage
from .nodes.holaf_save_video import HolafSaveVideo
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
from .nodes.holaf_ratio_calculator import HolafRatioCalculator
from .nodes.holaf_bypasser import HolafBypasser
from .nodes.holaf_group_bypasser import HolafGroupBypasser
from .nodes.holaf_remote import HolafRemote
from .nodes.holaf_shortcut import HolafShortcut
from .nodes.holaf_shortcut_user import HolafShortcutUser
from .nodes.holaf_load_image_video import HolafLoadImageVideo
from .nodes.holaf_image_batch_slice import HolafImageBatchSlice
from .nodes.holaf_video_preview import HolafVideoPreview


# Maps internal class names to the node's implementation.
NODE_CLASS_MAPPINGS = {
    "HolafSaveImage": HolafSaveImage,
    "HolafSaveVideo": HolafSaveVideo,
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
    "HolafRatioCalculator": HolafRatioCalculator,
    "HolafBypasser": HolafBypasser,
    "HolafGroupBypasser": HolafGroupBypasser,
    "HolafRemote": HolafRemote,
    "HolafShortcut": HolafShortcut,
    "HolafShortcutUser": HolafShortcutUser,
    "HolafLoadImageVideo": HolafLoadImageVideo,
    "HolafImageBatchSlice": HolafImageBatchSlice,
    "HolafVideoPreview": HolafVideoPreview,
}

# Maps internal class names to a user-friendly display name for the ComfyUI menu.
NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafSaveImage": "Save Image (Holaf)",
    "HolafSaveVideo": "Save Video (Holaf)",
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
    "HolafRatioCalculator": "Ratio Calculator (Holaf)",
    "HolafBypasser": "Bypasser (Holaf)",
    "HolafGroupBypasser": "Group Bypasser (Holaf)",
    "HolafRemote": "Remote (Holaf)",
    "HolafShortcut": "Shortcut (Holaf)",
    "HolafShortcutUser": "Shortcut User (Holaf)",
    "HolafLoadImageVideo": "Load Image/Video (Holaf)",
    "HolafImageBatchSlice": "Image Batch Slice (Holaf)",
    "HolafVideoPreview": "Video Preview (Holaf)",
}

# The WEB_DIRECTORY tells ComfyUI where to look for JavaScript files that correspond to the Python nodes.
WEB_DIRECTORY = "./js"

# Indicate successful loading in the console.
print("✅ Holaf Custom Nodes initialized")

# Export mappings for ComfyUI to use.
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']