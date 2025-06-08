# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-23
#
# Purpose:
# This file defines the 'HolafLutGenerator' custom node for ComfyUI.
# It creates a 3D Look-Up Table (LUT) using one of two methods:
# 1. Look Transfer: If only a reference_image is provided, it transfers its color
#    profile to a neutral grid using histogram matching.
# 2. Difference/Calibration: If a neutral_image AND a modified reference_image
#    are provided, it calculates the color transformation between them to create the LUT.
#
# How it works (Difference Mode - CORRECTED LOGIC):
# 1. It iterates through every pixel of the provided neutral and graded images.
# 2. For each pixel, the color from the neutral image is treated as an INPUT coordinate
#    in the 3D LUT space (after being scaled to the LUT size).
# 3. The color from the graded image at the same pixel location is the desired OUTPUT value.
# 4. It populates the 3D LUT by mapping every input coordinate found to its
#    corresponding output value. This correctly captures any manual color grading.
# === End Documentation ===

import torch
import numpy as np
from PIL import Image, ImageEnhance, ImageStat
import math

class HolafLutGenerator:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "reference_image": ("IMAGE",),
                "lut_size": ("INT", {"default": 64, "min": 16, "max": 128, "step": 16}),
                "title": ("STRING", {"default": "Generated LUT"}),
            },
            "optional": {
                "neutral_image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("HOLAF_LUT_DATA", "IMAGE", "IMAGE",)
    RETURN_NAMES = ("holaf_lut_data", "reference_image", "neutral_image_out",)
    FUNCTION = "generate_lut"
    CATEGORY = "Holaf/LUT"

    # --- Helper Functions ---
    def tensor_to_pil(self, tensor: torch.Tensor) -> Image.Image:
        if tensor.ndim == 4:
            tensor = tensor[0]
        image_np = (tensor.cpu().numpy() * 255.0).astype(np.uint8)
        return Image.fromarray(image_np, 'RGB' if image_np.shape[2] == 3 else 'RGBA')

    def pil_to_tensor(self, image: Image.Image) -> torch.Tensor:
        image_np = np.array(image).astype(np.float32) / 255.0
        return torch.from_numpy(image_np).unsqueeze(0)

    def _generate_hald_clut_image(self, size: int) -> Image.Image:
        dim = int(round(size ** 1.5))
        hald_clut = np.zeros((dim, dim, 3), dtype=np.uint8)
        step = 255.0 / (size - 1)
        for b in range(size):
            for g in range(size):
                for r in range(size):
                    x = (b % int(dim/size)) * size + r
                    y = (b // int(dim/size)) * size + g
                    if x < dim and y < dim:
                        hald_clut[y, x, 0] = int(r * step)
                        hald_clut[y, x, 1] = int(g * step)
                        hald_clut[y, x, 2] = int(b * step)
        return Image.fromarray(hald_clut, 'RGB')
    
    def _match_histograms_numpy(self, source_np: np.ndarray, reference_np: np.ndarray) -> np.ndarray:
        matched_channels = []
        for i in range(source_np.shape[2]):
            source_channel = source_np[:, :, i]
            ref_channel = reference_np[:, :, i]
            source_values, bin_idx, source_counts = np.unique(source_channel, return_inverse=True, return_counts=True)
            ref_values, ref_counts = np.unique(ref_channel, return_counts=True)
            source_cdf = np.cumsum(source_counts).astype(np.float64) / source_channel.size
            ref_cdf = np.cumsum(ref_counts).astype(np.float64) / ref_channel.size
            interpolated_values = np.interp(source_cdf, ref_cdf, ref_values)
            matched_channel = interpolated_values[bin_idx].reshape(source_channel.shape)
            matched_channels.append(matched_channel)
        matched_np = np.stack(matched_channels, axis=-1).astype(np.uint8)
        return matched_np

    # --- Main Execution Function (FINAL CORRECTED LOGIC) ---
    def generate_lut(self, reference_image: torch.Tensor, lut_size: int, title: str, neutral_image: torch.Tensor = None):
        graded_pil = self.tensor_to_pil(reference_image[0]).convert("RGB")
        
        final_lut_np = np.zeros((lut_size, lut_size, lut_size, 3), dtype=np.float32)
        neutral_image_for_output = None

        if neutral_image is not None:
            # --- DIFFERENCE MODE ---
            print(f"[HolafLutGenerator] Difference Mode activated.")
            neutral_pil = self.tensor_to_pil(neutral_image[0]).convert("RGB")
            
            if graded_pil.size != neutral_pil.size:
                print(f"[HolafLutGenerator] Warning: Graded image size {graded_pil.size} differs from neutral {neutral_pil.size}. Resizing graded image to match.")
                graded_pil = graded_pil.resize(neutral_pil.size, Image.Resampling.LANCZOS)
            
            # Convert both images to NumPy arrays for efficient processing
            neutral_np_uint8 = np.array(neutral_pil)
            graded_np_uint8 = np.array(graded_pil)

            # Flatten the arrays to iterate over pixels
            neutral_pixels = neutral_np_uint8.reshape(-1, 3)
            graded_pixels = graded_np_uint8.reshape(-1, 3)

            # Scale factor to map 0-255 pixel values to 0-(lut_size-1) indices
            scale = (lut_size - 1) / 255.0

            # Use the colors from the neutral image as coordinates to populate the LUT
            for i in range(neutral_pixels.shape[0]):
                # Get the original color (our address)
                r_in, g_in, b_in = neutral_pixels[i]
                
                # Get the new color (our value)
                r_out, g_out, b_out = graded_pixels[i]
                
                # Convert original color to LUT indices
                r_idx = int(round(r_in * scale))
                g_idx = int(round(g_in * scale))
                b_idx = int(round(b_in * scale))
                
                # Assign the new color value to the correct spot in the LUT
                # The value is normalized to [0, 1] for the LUT data
                final_lut_np[b_idx, g_idx, r_idx] = [r_out / 255.0, g_out / 255.0, b_out / 255.0]

            neutral_image_for_output = neutral_image

        else:
            # --- LOOK TRANSFER MODE ---
            print(f"[HolafLutGenerator] Look Transfer Mode activated with Histogram Matching.")
            neutral_pil = self._generate_hald_clut_image(lut_size)
            neutral_np = np.array(neutral_pil)
            graded_np = np.array(graded_pil)
            
            color_matched_np = self._match_histograms_numpy(neutral_np, graded_np)
            modified_lut_pil = Image.fromarray(color_matched_np, 'RGB')
            
            # Rebuild LUT from the generated image
            dim = modified_lut_pil.width
            grid_size = int(round(dim / lut_size))
            for b_idx in range(lut_size):
                for g_idx in range(lut_size):
                    for r_idx in range(lut_size):
                        x = (b_idx % grid_size) * lut_size + r_idx
                        y = (b_idx // grid_size) * lut_size + g_idx
                        if x < dim and y < modified_lut_pil.height:
                            pixel_value = modified_lut_pil.getpixel((x, y))
                            final_lut_np[b_idx, g_idx, r_idx] = np.array(pixel_value, dtype=np.float32) / 255.0

            neutral_image_for_output = self.pil_to_tensor(neutral_pil)
        
        holaf_lut_data = {
            "lut": final_lut_np,
            "size": lut_size,
            "title": title
        }
        
        print(f"[HolafLutGenerator] LUT '{title}' (Size: {lut_size}) processed successfully.")
        return (holaf_lut_data, reference_image, neutral_image_for_output,)