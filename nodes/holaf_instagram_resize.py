# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-21
#
# Purpose:
# This file defines the 'HolafInstagramResize' custom node for ComfyUI.
# It resizes an image to the closest Instagram-compatible ratio (1:1, 4:5, or 16:9)
# without cropping, adding colored bars (letterboxing or pillarboxing) to fill the empty space.
#
# Features:
# - Automatic ratio selection: Determines the closest Instagram-compatible ratio to the input image.
# - Color filling: Adds colored bars to maintain the aspect ratio without cropping.
# - User-defined fill color: Allows the user to specify the fill color.
# - Automatic color selection: Option to automatically choose a fill color based on the image content.
#
# === End Documentation ===

import torch
from PIL import Image, ImageColor
import numpy as np

class HolafInstagramResize:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "fill_color": ("STRING", {"default": "black"}),  # String for color names
                "auto_color": ("BOOLEAN", {"default": False}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "resize_image"
    CATEGORY = "Holaf"

    def resize_image(self, image, fill_color, auto_color):
        # Convert tensor to PIL image
        img_array = image.cpu().numpy() * 255.0
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        img = Image.fromarray(img_array[0]) # Assuming a batch size of 1 for now

        # Get image dimensions
        width, height = img.size
        aspect_ratio = width / height

        # Define Instagram-compatible ratios
        ratios = {
            "1:1": 1.0,
            "4:5": 0.8,
            "16:9": 1.7777777777777777,
        }

        # Determine the closest ratio
        closest_ratio_name = min(ratios, key=lambda k: abs(ratios[k] - aspect_ratio))
        closest_ratio = ratios[closest_ratio_name]

        # Calculate the dimensions of the final canvas to fit the original image + padding
        if aspect_ratio > closest_ratio:
            # Image is wider than the target ratio. Needs letterboxing (bars top/bottom).
            # Final canvas width = original width.
            # Final canvas height = original width / target ratio.
            final_width = width
            final_height = int(round(width / closest_ratio)) # Use round for better accuracy
        elif aspect_ratio < closest_ratio:
            # Image is taller than the target ratio. Needs pillarboxing (bars left/right).
            # Final canvas height = original height.
            # Final canvas width = original height * target ratio.
            final_width = int(round(height * closest_ratio)) # Use round for better accuracy
            final_height = height
        else:
             # Image already matches the target ratio
             final_width = width
             final_height = height


        # Determine fill color
        if auto_color:
            fill_color = self.get_dominant_edge_color(img)
            if fill_color is None:
                fill_color = "black"

        # Parse fill color string
        try:
            fill_color_rgb = ImageColor.getcolor(fill_color, "RGB")
        except ValueError:
            print(f"[Holaf Instagram Resize] Invalid color name: {fill_color}. Using black instead.")
            fill_color_rgb = (0, 0, 0)  # Black

        # Create a new image with the FINAL dimensions and fill color
        resized_img = Image.new("RGB", (final_width, final_height), fill_color_rgb)

        # Calculate the position to paste the original image onto the new canvas
        x_offset = (final_width - width) // 2
        y_offset = (final_height - height) // 2

        # Paste the original image onto the center of the new image
        resized_img.paste(img, (x_offset, y_offset))

        # Convert back to tensor
        resized_img_array = np.array(resized_img).astype(np.float32) / 255.0
        resized_img_array = np.expand_dims(resized_img_array, axis=0)  # Add batch dimension
        resized_img_tensor = torch.from_numpy(resized_img_array).float()

        return (resized_img_tensor,)

    # === Helper Functions (To be implemented later) ===
    def get_dominant_edge_color(self, image):
        """
        Analyzes the image to determine the dominant color along the edges.
        Returns the average color as a string (e.g., "rgb(255, 0, 0)").
        """
        width, height = image.size

        # Extract pixel data from the edges
        pixels_top = list(image.getdata())[:width]
        pixels_bottom = list(image.getdata())[width * (height - 1):]
        pixels_left = [image.getpixel((0, y)) for y in range(height)]
        pixels_right = [image.getpixel((width - 1, y)) for y in range(height)]

        # Combine all edge pixels
        all_edge_pixels = pixels_top + pixels_bottom + pixels_left + pixels_right

        # Calculate the average color
        r_values = [pixel[0] for pixel in all_edge_pixels]
        g_values = [pixel[1] for pixel in all_edge_pixels]
        b_values = [pixel[2] for pixel in all_edge_pixels]

        average_r = int(sum(r_values) / len(r_values))
        average_g = int(sum(g_values) / len(g_values))
        average_b = int(sum(b_values) / len(b_values))

        return f"rgb({average_r}, {average_g}, {average_b})"
