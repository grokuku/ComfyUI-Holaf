# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-23
#
# Purpose:
# This file defines the 'HolafLutApplier' custom node for ComfyUI.
# It applies a 3D Look-Up Table (LUT) to a source image.
#
# How it works:
# This version has been updated for maximum compatibility. Instead of relying on a
# specific version of Pillow's ImageCms engine, it now uses a manual trilinear
# interpolation method implemented with NumPy. This ensures consistent results
# across different environments.
#
# 1. Input: Takes a source image and a 'HOLAF_LUT_DATA' object.
# 2. Pre-computation: The image pixel values (0-1 float) are scaled by the LUT size
#    to get coordinates within the LUT grid.
# 3. Trilinear Interpolation: For each pixel in the source image, it finds the
#    8 surrounding points (the "cubelet") in the 3D LUT. It then interpolates
#    between these 8 points based on the pixel's exact color position to calculate
#    the final output color. This is done efficiently for the entire image using NumPy.
# 4. Intensity Control: An 'intensity' slider allows blending the original
#    image with the LUT-transformed image.
#
# Design Choices:
# - NumPy for Compatibility: Using a manual NumPy-based trilinear interpolation
#   removes the dependency on a specific version of the Pillow-SIMD or Pillow
#   library's C-based color engine, resolving potential 'AttributeError' issues.
# - Performance: The interpolation is vectorized using NumPy for good performance,
#   though it may be slightly slower than a native C implementation like LittleCMS.
# === End Documentation ===

import torch
import numpy as np
from PIL import Image
import math

class HolafLutApplier:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "holaf_lut_data": ("HOLAF_LUT_DATA",),
                "intensity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "display": "slider"}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("modified_image",)
    FUNCTION = "apply_lut"
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

    # --- New Trilinear Interpolation Function ---
    def _trilinear_interpolation(self, image_np: np.ndarray, lut_np: np.ndarray, lut_size: int) -> np.ndarray:
        """
        Applies a 3D LUT to an image using trilinear interpolation with NumPy.
        Args:
            image_np: Source image as a NumPy array (H, W, 3) with float values in [0, 1].
            lut_np: 3D LUT as a NumPy array (size, size, size, 3) with float values in [0, 1].
            lut_size: The size of one dimension of the LUT grid (e.g., 64).
        Returns:
            The color-corrected image as a NumPy array (H, W, 3) with float values in [0, 1].
        """
        # Scale image values to LUT coordinates
        scaled_coords = image_np * (lut_size - 1)
        
        # Get integer and fractional parts of coordinates
        coords_floor = np.floor(scaled_coords).astype(int)
        coords_fract = scaled_coords - coords_floor

        # Clip coordinates to be within LUT bounds
        coords_floor = np.clip(coords_floor, 0, lut_size - 2)
        
        # Get the 8 corner points of the cubelet for each pixel
        b0, g0, r0 = coords_floor[..., 2], coords_floor[..., 1], coords_floor[..., 0]
        b1, g1, r1 = b0 + 1, g0 + 1, r0 + 1
        
        # Get LUT values at the 8 corners
        c000 = lut_np[b0, g0, r0]
        c001 = lut_np[b0, g0, r1]
        c010 = lut_np[b0, g1, r0]
        c011 = lut_np[b0, g1, r1]
        c100 = lut_np[b1, g0, r0]
        c101 = lut_np[b1, g0, r1]
        c110 = lut_np[b1, g1, r0]
        c111 = lut_np[b1, g1, r1]
        
        # Get interpolation weights (remap fractional part to new axis)
        wr = coords_fract[..., 0][..., np.newaxis]
        wg = coords_fract[..., 1][..., np.newaxis]
        wb = coords_fract[..., 2][..., np.newaxis]

        # Interpolate along the R-axis
        c00 = c000 * (1 - wr) + c001 * wr
        c01 = c010 * (1 - wr) + c011 * wr
        c10 = c100 * (1 - wr) + c101 * wr
        c11 = c110 * (1 - wr) + c111 * wr
        
        # Interpolate along the G-axis
        c0 = c00 * (1 - wg) + c01 * wg
        c1 = c10 * (1 - wg) + c11 * wg
        
        # Interpolate along the B-axis
        c = c0 * (1 - wb) + c1 * wb
        
        return np.clip(c, 0.0, 1.0)

    # --- Main LUT Application Logic (Updated for Compatibility) ---
    def apply_lut(self, image: torch.Tensor, holaf_lut_data: dict, intensity: float):
        if intensity == 0.0:
            return (image,)
            
        if not isinstance(holaf_lut_data, dict) or not all(k in holaf_lut_data for k in ['lut', 'size']):
            raise ValueError("Invalid HOLAF_LUT_DATA input. Expected a dict with 'lut' and 'size' keys.")

        lut_np = holaf_lut_data.get('lut')
        lut_size = holaf_lut_data.get('size')

        if not isinstance(lut_np, np.ndarray) or not isinstance(lut_size, int) or lut_size == 0:
            raise ValueError("Malformed HOLAF_LUT_DATA content.")
        
        # Convert the source tensor to a NumPy array in the range [0, 1]
        source_np_b, source_np_h, source_np_w, source_np_c = image.shape
        source_np = image[0].cpu().numpy() # Work on the first image of the batch

        # Apply the LUT using our NumPy-based interpolation
        modified_np = self._trilinear_interpolation(source_np, lut_np, lut_size)

        # --- Blending based on intensity ---
        if intensity < 1.0:
            final_np = source_np * (1.0 - intensity) + modified_np * intensity
        else:
            final_np = modified_np
        
        # Convert the final NumPy array back to a tensor
        result_tensor = torch.from_numpy(final_np).unsqueeze(0).to(image.device)

        return (result_tensor,)