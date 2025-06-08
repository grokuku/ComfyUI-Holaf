from nodes import PreviewImage
import os

# --- Node Definition ---
class HolafImageComparer(PreviewImage):
  """
  A custom node that displays two sets of images in the UI for comparison.
  It also acts as a passthrough node for the input images.
  """

  # Define the node's display name and category in the ComfyUI menu.
  NAME = 'image comparer (holaf)'
  CATEGORY = 'holaf'
  FUNCTION = "compare_images"

  # Define the output slots of the node.
  RETURN_TYPES = ("IMAGE", "IMAGE",)
  RETURN_NAMES = ("image_a", "image_b",)

  @classmethod
  def INPUT_TYPES(cls):
    """
    Defines the input slots for the node.
    It takes two optional image inputs and hidden prompt/info inputs.
    """
    return {
      "required": {},
      "optional": {
        "image_a": ("IMAGE",),
        "image_b": ("IMAGE",),
      },
      "hidden": {
        "prompt": "PROMPT",
        "extra_pnginfo": "EXTRA_PNGINFO"
      },
    }

  def compare_images(self,
                     image_a=None,
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
    if image_a is not None and len(image_a) > 0:
      saved_a = self.save_images(image_a, filename_prefix + "a_", prompt, extra_pnginfo)
      ui_data['a_images'] = saved_a.get('ui', {}).get('images', [])

    if image_b is not None and len(image_b) > 0:
      saved_b = self.save_images(image_b, filename_prefix + "b_", prompt, extra_pnginfo)
      ui_data['b_images'] = saved_b.get('ui', {}).get('images', [])
      
    # Return a dictionary compliant with ComfyUI's custom node standards:
    # 'ui' key holds data for the frontend javascript widget.
    # 'result' key holds the data for the node's output connectors.
    return { "ui": ui_data, "result": (image_a, image_b) }

# This mapping is used by __init__.py to register the node with ComfyUI.
NODE_CLASS_MAPPINGS = {
  'HolafImageComparer': HolafImageComparer,
}