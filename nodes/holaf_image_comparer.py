# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-01
#
# Purpose:
# This file defines the 'HolafImageComparer' custom node for ComfyUI.
# Its primary function is to provide a user interface element that allows
# for the side-by-side comparison of two sets of images (image_a and image_b).
# This version also acts as a passthrough node, making the input images
# available as outputs.
#
# Design Choices & Rationale:
# - Inheritance: Inherits from the standard ComfyUI 'PreviewImage' node.
#   This leverages the existing image saving and preview infrastructure,
#   reducing code duplication and ensuring compatibility with ComfyUI's
#   image handling mechanisms.
# - Inputs: Takes two optional 'IMAGE' inputs ('image_a', 'image_b').
#   Making them optional allows the node to function even if only one
#   or neither input is connected, providing flexibility in workflow design.
# - Processing: The 'compare_images' method utilizes the inherited 'save_images'
#   function. It saves each input image set separately, likely using distinct
#   filename prefixes ("a_", "b_") to differentiate them in the output directory.
# - Output: Returns a dictionary structured specifically for ComfyUI's execution model.
#   - The 'ui' key contains data {'a_images': [...], 'b_images': [...]} for the JavaScript frontend.
#   - The 'result' key contains a tuple with the passthrough images (image_a, image_b)
#     for the node's output connectors.
# - Helpers: Includes utility functions for naming (`get_name`), categorization (`get_category`),
#   and colored logging (`log`) for potential debugging and organization, although
#   `get_name` is bypassed for the main class name.
# - Namespace: Uses a 'holaf' namespace for organization within ComfyUI.
# === End Documentation ===

# Combined Python code for holaf-comfy nodes

from nodes import PreviewImage
import os # Keep os import if needed by PreviewImage or save_images, otherwise remove

# --- Constants ---
NAMESPACE='holaf'

def get_name(name):
    """Helper to get node name with namespace."""
    return f'{name} ({NAMESPACE})'

def get_category(sub_dirs = None):
    """Helper to get node category."""
    if sub_dirs is None:
        return NAMESPACE
    else:
        # This sub_dirs logic might be removable if only one node exists
        return f"{NAMESPACE}/utils"

# --- Logging ---
# https://stackoverflow.com/questions/4842424/list-of-ansi-color-escape-sequences
# https://en.wikipedia.org/wiki/ANSI_escape_code#3-bit_and_4-bit
COLORS = {
  'BLACK': '\33[30m', 'RED': '\33[31m', 'GREEN': '\33[32m', 'YELLOW': '\33[33m',
  'BLUE': '\33[34m', 'MAGENTA': '\33[35m', 'CYAN': '\33[36m', 'WHITE': '\33[37m',
  'GREY': '\33[90m', 'BRIGHT_RED': '\33[91m', 'BRIGHT_GREEN': '\33[92m',
  'BRIGHT_YELLOW': '\33[93m', 'BRIGHT_BLUE': '\33[94m', 'BRIGHT_MAGENTA': '\33[95m',
  'BRIGHT_CYAN': '\33[96m', 'BRIGHT_WHITE': '\33[97m',
  'RESET': '\33[00m', 'BOLD': '\33[01m', 'NORMAL': '\33[22m', 'ITALIC': '\33[03m',
  'UNDERLINE': '\33[04m', 'BLINK': '\33[05m', 'BLINK2': '\33[06m', 'SELECTED': '\33[07m',
  'BG_BLACK': '\33[40m', 'BG_RED': '\33[41m', 'BG_GREEN': '\33[42m', 'BG_YELLOW': '\33[43m',
  'BG_BLUE': '\33[44m', 'BG_MAGENTA': '\33[45m', 'BG_CYAN': '\33[46m', 'BG_WHITE': '\33[47m',
  'BG_GREY': '\33[100m', 'BG_BRIGHT_RED': '\33[101m', 'BG_BRIGHT_GREEN': '\33[102m',
  'BG_BRIGHT_YELLOW': '\33[103m', 'BG_BRIGHT_BLUE': '\33[104m', 'BG_BRIGHT_MAGENTA': '\33[105m',
  'BG_BRIGHT_CYAN': '\33[106m', 'BG_BRIGHT_WHITE': '\33[107m',
}

def log(message, color=None, msg_color=None, prefix=None):
  """Basic logging."""
  color_code = COLORS.get(color, COLORS["BRIGHT_GREEN"])
  msg_color_code = COLORS.get(msg_color, '')
  prefix_str = f'[{prefix}]' if prefix is not None else ''
  msg = f'{color_code}[holaf-comfy]{prefix_str}'
  msg += f'{msg_color_code} {message}{COLORS["RESET"]}'
  print(msg)

# --- Node Definition ---
class HolafImageComparer(PreviewImage):
  """A node that compares two images in the UI."""

  # Set name directly, bypassing get_name to avoid namespace suffix
  NAME = 'image comparer (holaf)'
  CATEGORY = get_category() # Keep category helper for now
  FUNCTION = "compare_images"

  # <--- MODIFICATION : DÉCLARATION DES SORTIES --->
  RETURN_TYPES = ("IMAGE", "IMAGE",)
  RETURN_NAMES = ("image_a", "image_b",)
  # <--- FIN MODIFICATION --->

  @classmethod
  def INPUT_TYPES(cls):
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

    # Use the save_images method inherited from PreviewImage
    ui_data = { "a_images":[], "b_images": [] }
    if image_a is not None and len(image_a) > 0:
      # Assuming save_images returns a dict like {'ui': {'images': [...]}}
      saved_a = self.save_images(image_a, filename_prefix + "a_", prompt, extra_pnginfo)
      ui_data['a_images'] = saved_a.get('ui', {}).get('images', [])

    if image_b is not None and len(image_b) > 0:
      saved_b = self.save_images(image_b, filename_prefix + "b_", prompt, extra_pnginfo)
      ui_data['b_images'] = saved_b.get('ui', {}).get('images', [])
      
    # <--- MODIFICATION : NOUVELLE STRUCTURE DE RETOUR --->
    # Return a dictionary with 'ui' for the frontend and 'result' for the node outputs.
    return { "ui": ui_data, "result": (image_a, image_b) }
    # <--- FIN MODIFICATION --->

# --- Export Mapping ---
# This mapping will be imported by __init__.py
NODE_CLASS_MAPPINGS = {
  'HolafImageComparer': HolafImageComparer, # Use the class name as the key
}

# Optional: Add a log message for when this module is loaded if desired
# log("Holaf nodes module loaded.", color="BLUE")