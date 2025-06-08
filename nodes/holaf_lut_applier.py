import torch
import numpy as np
from PIL import Image

class HolafLutApplier:
    """
    Applies a 3D Look-Up Table (LUT) to an image for color grading.
    It uses a pure NumPy implementation of trilinear interpolation to ensure
    compatibility and avoid external library issues (e.g., LittleCMS).
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                # A custom data type containing the LUT np.ndarray and its grid size.
                "holaf_lut_data": ("HOLAF_LUT_DATA",),
                # Controls the blend between the original and the color-graded image.
                "intensity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "display": "slider"}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("modified_image",)
    FUNCTION = "apply_lut"
    CATEGORY = "Holaf/LUT"

    def _trilinear_interpolation(self, image_np: np.ndarray, lut_np: np.ndarray, lut_size: int) -> np.ndarray:
        """
        Applies a 3D LUT to an image using NumPy-based trilinear interpolation.

        For each pixel, this function finds its corresponding location within the LUT cube,
        identifies the 8 surrounding grid points, and interpolates their values to
        determine the final output color.
        """
        # Scale image's [0, 1] color values to LUT grid coordinates [0, lut_size-1].
        scaled_coords = image_np * (lut_size - 1)
        
        # Split coordinates into integer (grid indices) and fractional (interpolation weights) parts.
        coords_floor = np.floor(scaled_coords).astype(int)
        coords_fract = scaled_coords - coords_floor

        # Clip coordinates to prevent out-of-bounds errors at the upper edge.
        coords_floor = np.clip(coords_floor, 0, lut_size - 2)
        
        # Get indices for the 8 corner points of the cube surrounding each pixel's coordinate.
        b0, g0, r0 = coords_floor[..., 2], coords_floor[..., 1], coords_floor[..., 0]
        b1, g1, r1 = b0 + 1, g0 + 1, r0 + 1
        
        # Retrieve the color values from the LUT at these 8 corner points.
        c000 = lut_np[b0, g0, r0]
        c001 = lut_np[b0, g0, r1]
        c010 = lut_np[b0, g1, r0]
        c011 = lut_np[b0, g1, r1]
        c100 = lut_np[b1, g0, r0]
        c101 = lut_np[b1, g0, r1]
        c110 = lut_np[b1, g1, r0]
        c111 = lut_np[b1, g1, r1]
        
        # Get fractional parts as interpolation weights for each axis.
        wr = coords_fract[..., 0][..., np.newaxis]
        wg = coords_fract[..., 1][..., np.newaxis]
        wb = coords_fract[..., 2][..., np.newaxis]

        # Perform trilinear interpolation:
        # 1. Interpolate along the Red axis.
        c00 = c000 * (1 - wr) + c001 * wr
        c01 = c010 * (1 - wr) + c011 * wr
        c10 = c100 * (1 - wr) + c101 * wr
        c11 = c110 * (1 - wr) + c111 * wr
        # 2. Interpolate along the Green axis.
        c0 = c00 * (1 - wg) + c01 * wg
        c1 = c10 * (1 - wg) + c11 * wg
        # 3. Interpolate along the Blue axis.
        c = c0 * (1 - wb) + c1 * wb
        
        return np.clip(c, 0.0, 1.0)

    def apply_lut(self, image: torch.Tensor, holaf_lut_data: dict, intensity: float):
        # If intensity is 0, no effect is needed. Return the original image.
        if intensity == 0.0:
            return (image,)
            
        # Validate the structure of the incoming LUT data.
        if not isinstance(holaf_lut_data, dict) or not all(k in holaf_lut_data for k in ['lut', 'size']):
            raise ValueError("Invalid HOLAF_LUT_DATA input. Expected a dict with 'lut' and 'size' keys.")

        lut_np = holaf_lut_data.get('lut')
        lut_size = holaf_lut_data.get('size')

        if not isinstance(lut_np, np.ndarray) or not isinstance(lut_size, int) or lut_size == 0:
            raise ValueError("Malformed HOLAF_LUT_DATA content.")
        
        # Convert the source tensor to a NumPy array (H, W, C) in the range [0, 1] for processing.
        source_np = image[0].cpu().numpy()

        # Apply the LUT using our NumPy-based interpolation function.
        modified_np = self._trilinear_interpolation(source_np, lut_np, lut_size)

        # Blend the original and modified images based on the intensity slider.
        if intensity < 1.0:
            final_np = source_np * (1.0 - intensity) + modified_np * intensity
        else:
            final_np = modified_np
        
        # Convert the final NumPy array back to a ComfyUI-compatible tensor.
        result_tensor = torch.from_numpy(final_np).unsqueeze(0).to(image.device)

        return (result_tensor,)