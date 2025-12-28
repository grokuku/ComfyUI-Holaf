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
# 

from nodes import PreviewImage
import os

# --- Node Definition ---
class HolafImageComparer(PreviewImage):
  """
  A custom node that displays two sets of images in the UI for comparison.
  It also acts as a passthrough node for the input images.
  If only image_a is provided, it acts as a standard preview bridge.
  """

  # Define the node's display name and category in the ComfyUI menu.
  NAME = 'image comparer (holaf)'
  CATEGORY = 'Holaf'
  FUNCTION = "compare_images"

  # Define the output slots of the node.
  RETURN_TYPES = ("IMAGE", "IMAGE",)
  RETURN_NAMES = ("image_a", "image_b",)

  @classmethod
  def INPUT_TYPES(cls):
    """
    Defines the input slots for the node.
    image_a is now required to ensure standard preview behavior at minimum.
    image_b is optional for comparison.
    """
    return {
      "required": {
        "image_a": ("IMAGE",),
      },
      "optional": {
        "image_b": ("IMAGE",),
      },
      "hidden": {
        "prompt": "PROMPT",
        "extra_pnginfo": "EXTRA_PNGINFO"
      },
    }

  def compare_images(self,
                     image_a,
                     image_b=None,
                     filename_prefix="holaf.compare.",
                     prompt=None,
                     extra_pnginfo=None):
    """
    The main execution method of the node.
    It saves the input images and prepares data for both the UI and the output slots.
    """

    # Utilize the save_images method inherited from the parent PreviewImage class.
    # The saved image data is prepared for the frontend widget.
    ui_data = { "a_images":[], "b_images": [] }
    
    # Process Image A (Required)
    if image_a is not None and len(image_a) > 0:
      saved_a = self.save_images(image_a, filename_prefix + "a_", prompt, extra_pnginfo)
      ui_data['a_images'] = saved_a.get('ui', {}).get('images', [])

    # Process Image B (Optional)
    if image_b is not None and len(image_b) > 0:
      saved_b = self.save_images(image_b, filename_prefix + "b_", prompt, extra_pnginfo)
      ui_data['b_images'] = saved_b.get('ui', {}).get('images', [])
      
    # Return a dictionary compliant with ComfyUI's custom node standards:
    # 'ui' key holds data for the frontend javascript widget.
    # 'result' key holds the data for the node's output connectors.
    # Note: If image_b is None, the second output will be None.
    return { "ui": ui_data, "result": (image_a, image_b) }

# This mapping is used by __init__.py to register the node with ComfyUI.
NODE_CLASS_MAPPINGS = {
  'HolafImageComparer': HolafImageComparer,
}