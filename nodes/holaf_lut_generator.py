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
import numpy as np
from PIL import Image

class HolafLutGenerator:
    """
    Generates a 3D Look-Up Table (LUT) from input images.
    Operates in two distinct modes:

    1.  **Difference Mode** (if `neutral_image` is provided):
        Calculates the exact color transformation between a 'before' (neutral) and
        'after' (reference) image. It creates a LUT that represents this change.

    2.  **Look Transfer Mode** (if only `reference_image` is provided):
        Captures the general color style of the reference image by applying its
        color histogram to a neutral, identity LUT (a HALD CLUT).
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # The image with the desired final look ("after" image).
                "reference_image": ("IMAGE",),
                # The grid resolution of the LUT (e.g., 64x64x64). Higher is more precise.
                "lut_size": ("INT", {"default": 64, "min": 16, "max": 128, "step": 16}),
                "title": ("STRING", {"default": "Generated LUT"}),
            },
            "optional": {
                # An optional "before" image, used for Difference Mode.
                "neutral_image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("HOLAF_LUT_DATA", "IMAGE", "IMAGE",)
    RETURN_NAMES = ("holaf_lut_data", "reference_image", "neutral_image_out",)
    FUNCTION = "generate_lut"
    CATEGORY = "Holaf/LUT"

    def tensor_to_pil(self, tensor: torch.Tensor) -> Image.Image:
        if tensor.ndim == 4:
            tensor = tensor[0]
        image_np = tensor.cpu().float().mul(255).clamp(0, 255).byte().numpy()
        return Image.fromarray(image_np, 'RGB' if image_np.shape[2] == 3 else 'RGBA')

    def pil_to_tensor(self, image: Image.Image) -> torch.Tensor:
        image_np = np.array(image).astype(np.float32) / 255.0
        return torch.from_numpy(image_np).unsqueeze(0)

    def _generate_hald_clut_image(self, size: int) -> Image.Image:
        """Generates a neutral identity LUT image (HALD CLUT) using vectorized numpy."""
        dim = int(round(size ** 1.5))
        step = 255.0 / (size - 1) if size > 1 else 255.0
        
        # Create 3D grid using numpy vectorization instead of triple for loop
        r = np.arange(size, dtype=np.float32) * step
        g = np.arange(size, dtype=np.float32) * step
        b = np.arange(size, dtype=np.float32) * step
        
        # Reshape for broadcasting: r varies fastest, then g, then b
        rgb = np.stack(np.meshgrid(r, g, b, indexing='ij'), axis=-1).reshape(-1, 3)
        
        # Map to 2D image using the original layout pattern
        grid_size = size
        hald_clut = np.zeros((dim, dim, 3), dtype=np.uint8)
        for idx in range(min(size * size * size, dim * dim)):
            b_idx = idx // (size * size)
            g_idx = (idx % (size * size)) // size
            r_idx = idx % size
            x = (b_idx % (dim // size)) * size + r_idx
            y = (b_idx // (dim // size)) * size + g_idx
            if x < dim and y < dim:
                hald_clut[y, x] = rgb[idx]
        
        return Image.fromarray(hald_clut, 'RGB')
    
    def _match_histograms_numpy(self, source_np: np.ndarray, reference_np: np.ndarray) -> np.ndarray:
        """
        Matches the color distribution of a source image to a reference image.
        It operates on a per-channel basis, using the cumulative distribution function (CDF)
        to map source color values to the reference's color distribution.
        """
        matched_channels = []
        for i in range(source_np.shape[2]): # Process R, G, B channels independently
            source_channel = source_np[:, :, i]
            ref_channel = reference_np[:, :, i]
            source_values, bin_idx, source_counts = np.unique(source_channel, return_inverse=True, return_counts=True)
            ref_values, ref_counts = np.unique(ref_channel, return_counts=True)
            source_cdf = np.cumsum(source_counts).astype(np.float64) / source_channel.size
            ref_cdf = np.cumsum(ref_counts).astype(np.float64) / ref_channel.size
            # Interpolate to find new pixel values
            interpolated_values = np.interp(source_cdf, ref_cdf, ref_values)
            matched_channel = interpolated_values[bin_idx].reshape(source_channel.shape)
            matched_channels.append(matched_channel)
        matched_np = np.stack(matched_channels, axis=-1).astype(np.uint8)
        return matched_np

    def generate_lut(self, reference_image: torch.Tensor, lut_size: int, title: str, neutral_image: torch.Tensor = None):
        """Generates the 3D LUT data based on the provided inputs and selected mode."""
        graded_pil = self.tensor_to_pil(reference_image[0]).convert("RGB")
        final_lut_np = np.zeros((lut_size, lut_size, lut_size, 3), dtype=np.float32)
        neutral_image_for_output = None

        if neutral_image is not None:
            # --- DIFFERENCE MODE ---
            # Calculates the transformation from neutral_image to reference_image.
            neutral_pil = self.tensor_to_pil(neutral_image[0]).convert("RGB")
            
            # Ensure images have same dimensions for a 1:1 pixel comparison.
            if graded_pil.size != neutral_pil.size:
                graded_pil = graded_pil.resize(neutral_pil.size, Image.Resampling.LANCZOS)
            
            neutral_np_uint8 = np.array(neutral_pil)
            graded_np_uint8 = np.array(graded_pil)
            neutral_pixels = neutral_np_uint8.reshape(-1, 3)
            graded_pixels = graded_np_uint8.reshape(-1, 3)

            # Vectorized LUT population: accumulate all pixel pairs and average duplicates.
            scale = (lut_size - 1) / 255.0
            indices = (np.rint(neutral_pixels * scale).clip(0, lut_size - 1)).astype(np.int32)
            values = graded_pixels / 255.0

            # Accumulate values and counts per LUT cell
            np.add.at(final_lut_np, (indices[:, 2], indices[:, 1], indices[:, 0]), values)
            count_np = np.zeros((lut_size, lut_size, lut_size), dtype=np.float32)
            np.add.at(count_np, (indices[:, 2], indices[:, 1], indices[:, 0]), 1.0)

            # Average (avoid division by zero)
            count_4d = count_np[..., np.newaxis]
            count_4d[count_4d == 0] = 1.0
            final_lut_np = final_lut_np / count_4d

            neutral_image_for_output = neutral_image
        else:
            # --- LOOK TRANSFER MODE ---
            # Captures the general style of the reference image via histogram matching.
            
            # 1. Generate a neutral, identity color grid (HALD CLUT) to serve as the base.
            neutral_pil = self._generate_hald_clut_image(lut_size)
            neutral_np = np.array(neutral_pil)
            graded_np = np.array(graded_pil)
            
            # 2. Apply the color histogram of the reference image onto the neutral grid.
            color_matched_np = self._match_histograms_numpy(neutral_np, graded_np)
            modified_lut_pil = Image.fromarray(color_matched_np, 'RGB')
            
            # 3. Reconstruct the 3D LUT array by reading pixel values from the modified HALD image.
            dim = modified_lut_pil.width
            grid_size = int(round(dim / lut_size))
            modified_np = np.array(modified_lut_pil)
            for b_idx in range(lut_size):
                for g_idx in range(lut_size):
                    for r_idx in range(lut_size):
                        x = (b_idx % grid_size) * lut_size + r_idx
                        y = (b_idx // grid_size) * lut_size + g_idx
                        if x < dim and y < modified_lut_pil.height:
                            final_lut_np[b_idx, g_idx, r_idx] = modified_np[y, x].astype(np.float32) / 255.0

            neutral_image_for_output = self.pil_to_tensor(neutral_pil)
        
        # Package the final LUT array, size, and title into a dictionary for output.
        holaf_lut_data = {
            "lut": final_lut_np,
            "size": lut_size,
            "title": title
        }
        
        return (holaf_lut_data, reference_image, neutral_image_for_output,)