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

import torch
from PIL import Image, ImageColor
import numpy as np

class HolafInstagramResize:
    """
    Resizes an image to the nearest Instagram aspect ratio (1:1, 4:5, 16:9)
    by adding colored bars (letterboxing/pillarboxing) instead of cropping.
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                # The color for the background bars (e.g., "black", "#FF0000").
                "fill_color": ("STRING", {"default": "black"}),
                # If True, automatically determines the fill color from the image's edges.
                "auto_color": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "resize_image"
    CATEGORY = "Holaf"

    def resize_image(self, image, fill_color, auto_color):
        # Convert the input tensor (Batch, H, W, C) to a single PIL Image.
        img_array = image.cpu().numpy() * 255.0
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        img = Image.fromarray(img_array[0])

        width, height = img.size
        aspect_ratio = width / height

        # Define the target Instagram-compatible ratios.
        ratios = {
            "1:1": 1.0,
            "4:5": 0.8,
            "16:9": 1.7777777777777777,
        }

        # Find the closest target ratio to the image's current ratio.
        closest_ratio_name = min(ratios, key=lambda k: abs(ratios[k] - aspect_ratio))
        closest_ratio = ratios[closest_ratio_name]

        # Calculate the final canvas dimensions.
        if aspect_ratio > closest_ratio:
            # Image is wider than the target: needs letterboxing (bars top/bottom).
            # The canvas width is the original image width.
            # The canvas height is calculated based on the target ratio.
            final_width = width
            final_height = int(round(width / closest_ratio))
        elif aspect_ratio < closest_ratio:
            # Image is taller than the target: needs pillarboxing (bars left/right).
            # The canvas height is the original image height.
            # The canvas width is calculated based on the target ratio.
            final_width = int(round(height * closest_ratio))
            final_height = height
        else:
             # Image already matches the target ratio.
             final_width = width
             final_height = height

        # Determine the fill color.
        if auto_color:
            fill_color = self.get_dominant_edge_color(img)
            if fill_color is None:
                fill_color = "black"

        # Parse the color string and fall back to black if the color name is invalid.
        try:
            fill_color_rgb = ImageColor.getcolor(fill_color, "RGB")
        except ValueError:
            print(f"[Holaf Instagram Resize] Invalid color name: {fill_color}. Using black instead.")
            fill_color_rgb = (0, 0, 0)

        # Create a new blank canvas with the final dimensions and fill color.
        resized_img = Image.new("RGB", (final_width, final_height), fill_color_rgb)

        # Calculate offsets to center the original image on the new canvas.
        x_offset = (final_width - width) // 2
        y_offset = (final_height - height) // 2

        # Paste the original image onto the canvas.
        resized_img.paste(img, (x_offset, y_offset))

        # Convert the final PIL Image back to a torch tensor for ComfyUI.
        resized_img_array = np.array(resized_img).astype(np.float32) / 255.0
        resized_img_array = np.expand_dims(resized_img_array, axis=0)
        resized_img_tensor = torch.from_numpy(resized_img_array).float()

        return (resized_img_tensor,)

    def get_dominant_edge_color(self, image):
        """
        Analyzes the image edges to find the average color.
        """
        width, height = image.size

        # Collect all pixels from the top, bottom, left, and right edges.
        pixels_top = list(image.getdata())[:width]
        pixels_bottom = list(image.getdata())[width * (height - 1):]
        pixels_left = [image.getpixel((0, y)) for y in range(height)]
        pixels_right = [image.getpixel((width - 1, y)) for y in range(height)]
        all_edge_pixels = pixels_top + pixels_bottom + pixels_left + pixels_right

        # Calculate the average R, G, B values.
        r_values = [pixel[0] for pixel in all_edge_pixels]
        g_values = [pixel[1] for pixel in all_edge_pixels]
        b_values = [pixel[2] for pixel in all_edge_pixels]
        average_r = int(sum(r_values) / len(r_values))
        average_g = int(sum(g_values) / len(g_values))
        average_b = int(sum(b_values) / len(b_values))

        # Return the color as an "rgb(r,g,b)" string.
        return f"rgb({average_r}, {average_g}, {average_b})"