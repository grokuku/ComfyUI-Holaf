# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-23
#
# Purpose:
# This file defines the 'HolafColorMatcher' custom node for ComfyUI.
# It transfers the color characteristics (luminance, contrast, saturation, and overall color balance)
# from a reference image to a source image.
#
# Design Choices & Rationale:
# - Modular Effects: The matching process is broken down into four distinct components:
#   luminance, contrast, saturation, and color. Each can be toggled on/off.
# - Fine-Grained Control: Each component has a "mix" slider (0.0 to 1.0) allowing the user
#   to blend the effect, providing more creative control than a simple on/off switch.
# - Histogram Matching for Color: For the core "color" transfer, this node uses
#   histogram matching on a per-channel basis. This is a robust technique that adjusts
#   the source image's pixel intensity distribution to match the reference's distribution,
#   effectively transferring the overall mood, tint, and color balance. It's more powerful
#   than simply matching average hue. This is implemented using NumPy for efficiency.
# - Statistical Matching for Luma/Contrast/Saturation:
#   - Luminance/Contrast: Calculated from the L channel of the image (in L*a*b* or similar space,
#     approximated here via PIL's 'L' mode) using mean and standard deviation. The source
#     is then adjusted to match the target's statistics.
#   - Saturation: Calculated from the S channel in HSV color space.
# - Batch Processing: The node correctly handles batches of images. If the source and reference
#   batch sizes differ, it broadcasts the smaller batch to match the larger one.
# - Optional Masking: An optional `mask` input allows applying the color matching effect
#   only to specific regions of the source image.
# - Dependencies: Relies on standard libraries like Pillow (PIL), NumPy, and Torch, which
#   are already part of the ComfyUI ecosystem. This avoids adding new, heavy dependencies.
# - Helper Functions: Includes robust `tensor_to_pil` and `pil_to_tensor` helpers to ensure
#   compatibility with ComfyUI's image tensor format (BHWC).
# === End Documentation ===

import torch
import numpy as np
from PIL import Image, ImageEnhance, ImageStat, ImageOps

class HolafColorMatcher:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "reference_image": ("IMAGE",),
                "match_color": ("BOOLEAN", {"default": True}),
                "color_mix": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "display": "slider"}),
                "match_saturation": ("BOOLEAN", {"default": True}),
                "saturation_mix": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "display": "slider"}),
                "match_contrast": ("BOOLEAN", {"default": True}),
                "contrast_mix": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "display": "slider"}),
                "match_luminance": ("BOOLEAN", {"default": True}),
                "luminance_mix": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "display": "slider"}),
            },
            "optional": {
                "mask": ("MASK",),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("modified_image",)
    FUNCTION = "apply_color_match"
    CATEGORY = "Holaf"

    # --- Helper Functions ---

    def tensor_to_pil(self, tensor: torch.Tensor) -> Image.Image:
        if not isinstance(tensor, torch.Tensor):
            raise TypeError(f"Input must be a torch.Tensor, got {type(tensor)}")
        if tensor.ndim == 4:
            tensor = tensor[0] # Work with the first image in the batch
        
        image_np = tensor.cpu().numpy()
        if image_np.dtype == np.float32:
            image_np = (np.clip(image_np, 0.0, 1.0) * 255.0).astype(np.uint8)
        
        if image_np.ndim == 3 and image_np.shape[2] == 1:
            return Image.fromarray(image_np[:, :, 0], 'L')
        elif image_np.ndim == 3 and image_np.shape[2] in [3, 4]:
            return Image.fromarray(image_np, 'RGB' if image_np.shape[2] == 3 else 'RGBA')
        elif image_np.ndim == 2:
            return Image.fromarray(image_np, 'L')
        else:
            raise ValueError(f"Unsupported numpy array shape for PIL conversion: {image_np.shape}")

    def pil_to_tensor(self, image: Image.Image) -> torch.Tensor:
        image_np = np.array(image).astype(np.float32) / 255.0
        if image_np.ndim == 2:
            image_np = np.expand_dims(image_np, axis=2)
        tensor = torch.from_numpy(image_np)
        return tensor.unsqueeze(0) # Add batch dimension

    def _calculate_stats(self, pil_image: Image.Image):
        """Calculates luminance, contrast, and saturation for a PIL image."""
        # Luminance and Contrast
        img_lum_contrast = pil_image.convert("L")
        stat = ImageStat.Stat(img_lum_contrast)
        luminance = stat.mean[0]
        contrast = stat.stddev[0]

        # Saturation
        img_hsv = pil_image.convert("HSV")
        s_channel = np.array(img_hsv)[:, :, 1]
        saturation = np.mean(s_channel)

        return luminance, contrast, saturation

    def _match_histograms_numpy(self, source_np: np.ndarray, reference_np: np.ndarray) -> np.ndarray:
        """
        Matches the histogram of a source image to a reference image using NumPy.
        This is done on a per-channel basis.
        """
        matched_channels = []
        for i in range(source_np.shape[2]): # Iterate through R, G, B channels
            source_channel = source_np[:, :, i]
            ref_channel = reference_np[:, :, i]

            # Get the unique pixel values and their counts
            source_values, bin_idx, source_counts = np.unique(source_channel, return_inverse=True, return_counts=True)
            ref_values, ref_counts = np.unique(ref_channel, return_counts=True)

            # Calculate the cumulative distribution functions (CDFs)
            source_cdf = np.cumsum(source_counts).astype(np.float64) / source_channel.size
            ref_cdf = np.cumsum(ref_counts).astype(np.float64) / ref_channel.size

            # Interpolate to map source CDF to reference values
            interpolated_values = np.interp(source_cdf, ref_cdf, ref_values)

            # Map the source image to the new values
            matched_channel = interpolated_values[bin_idx].reshape(source_channel.shape)
            matched_channels.append(matched_channel)

        matched_np = np.stack(matched_channels, axis=-1).astype(np.uint8)
        return matched_np

    # --- Main Execution Function ---

    def apply_color_match(self, image: torch.Tensor, reference_image: torch.Tensor,
                          match_color: bool, color_mix: float,
                          match_saturation: bool, saturation_mix: float,
                          match_contrast: bool, contrast_mix: float,
                          match_luminance: bool, luminance_mix: float,
                          mask: torch.Tensor = None):

        batch_size_img = image.shape[0]
        batch_size_ref = reference_image.shape[0]

        # Handle batch size differences
        if batch_size_img > batch_size_ref:
            reference_image = reference_image.repeat(batch_size_img // batch_size_ref, 1, 1, 1)
        elif batch_size_ref > batch_size_img:
            image = image.repeat(batch_size_ref // batch_size_img, 1, 1, 1)

        batch_size = max(batch_size_img, batch_size_ref)
        
        if mask is not None and mask.shape[0] < batch_size:
            mask = mask.repeat(batch_size // mask.shape[0], 1, 1)

        output_images = []

        for i in range(batch_size):
            source_pil = self.tensor_to_pil(image[i]).convert("RGB")
            ref_pil = self.tensor_to_pil(reference_image[i]).convert("RGB")

            modified_pil = source_pil.copy()

            # --- 1. Color Matching (Histogram) ---
            if match_color and color_mix > 0:
                source_np = np.array(modified_pil)
                ref_np = np.array(ref_pil)
                color_matched_np = self._match_histograms_numpy(source_np, ref_np)
                color_matched_pil = Image.fromarray(color_matched_np, 'RGB')
                modified_pil = Image.blend(modified_pil, color_matched_pil, color_mix)

            src_lum, src_con, src_sat = self._calculate_stats(modified_pil) # Stats of currently modified image
            ref_lum, ref_con, ref_sat = self._calculate_stats(ref_pil) # Stats of reference

            # --- 2. Saturation Matching ---
            if match_saturation and saturation_mix > 0:
                if src_sat > 1e-5: # Avoid division by zero
                    sat_factor = ref_sat / src_sat
                    enhancer = ImageEnhance.Color(modified_pil)
                    sat_adjusted_pil = enhancer.enhance(sat_factor)
                    modified_pil = Image.blend(modified_pil, sat_adjusted_pil, saturation_mix)

            # --- 3. Contrast Matching ---
            if match_contrast and contrast_mix > 0:
                if src_con > 1e-5: # Avoid division by zero
                    con_factor = ref_con / src_con
                    enhancer = ImageEnhance.Contrast(modified_pil)
                    con_adjusted_pil = enhancer.enhance(con_factor)
                    modified_pil = Image.blend(modified_pil, con_adjusted_pil, contrast_mix)

            # --- 4. Luminance Matching ---
            if match_luminance and luminance_mix > 0:
                if src_lum > 1e-5: # Avoid division by zero
                    lum_factor = ref_lum / src_lum
                    enhancer = ImageEnhance.Brightness(modified_pil)
                    lum_adjusted_pil = enhancer.enhance(lum_factor)
                    modified_pil = Image.blend(modified_pil, lum_adjusted_pil, luminance_mix)
            
            # --- 5. Apply Mask ---
            if mask is not None:
                mask_pil = self.tensor_to_pil(mask[i]).convert("L")
                if mask_pil.size != source_pil.size:
                    mask_pil = mask_pil.resize(source_pil.size, Image.Resampling.LANCZOS)
                
                # Invert mask because paste uses the mask to define the area of pasting
                # We want to paste the modified image where the mask is white.
                # However, the blend happens on the whole image. So we paste the original back on top.
                final_pil_with_mask = modified_pil.copy()
                final_pil_with_mask.paste(source_pil, (0, 0), ImageOps.invert(mask_pil))
                modified_pil = final_pil_with_mask


            output_images.append(self.pil_to_tensor(modified_pil))
            
        final_tensor = torch.cat(output_images, dim=0)
        return (final_tensor,)