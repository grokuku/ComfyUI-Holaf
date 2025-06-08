import torch
import numpy as np
from PIL import Image, ImageEnhance, ImageStat, ImageOps

class HolafColorMatcher:
    """
    A node to transfer color characteristics (luminance, contrast, saturation,
    and overall color balance) from a reference image to a source image.
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        """
        Defines the input types for the node.
        Includes source and reference images, booleans to enable specific matches,
        mix sliders for intensity control, and an optional mask.
        """
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

    RETURN_TYPES = ("IMAGE", "IMAGE",)
    RETURN_NAMES = ("modified_image", "reference_image",)
    FUNCTION = "apply_color_match"
    CATEGORY = "Holaf"

    def tensor_to_pil(self, tensor: torch.Tensor) -> Image.Image:
        """Converts a ComfyUI image tensor (Batch, Height, Width, Channels) to a PIL Image."""
        if not isinstance(tensor, torch.Tensor):
            raise TypeError(f"Input must be a torch.Tensor, got {type(tensor)}")
        if tensor.ndim == 4:
            tensor = tensor[0]  # Process the first image in the batch
        
        image_np = tensor.cpu().numpy()
        if image_np.dtype == np.float32: # Convert float32 (0-1 range) to uint8 (0-255 range)
            image_np = (np.clip(image_np, 0.0, 1.0) * 255.0).astype(np.uint8)
        
        # Determine image mode based on channels
        if image_np.ndim == 3 and image_np.shape[2] == 1:
            return Image.fromarray(image_np[:, :, 0], 'L') # Grayscale
        elif image_np.ndim == 3 and image_np.shape[2] in [3, 4]:
            return Image.fromarray(image_np, 'RGB' if image_np.shape[2] == 3 else 'RGBA') # RGB or RGBA
        elif image_np.ndim == 2:
            return Image.fromarray(image_np, 'L') # Grayscale (if 2D array)
        else:
            raise ValueError(f"Unsupported numpy array shape for PIL conversion: {image_np.shape}")

    def pil_to_tensor(self, image: Image.Image) -> torch.Tensor:
        """Converts a PIL Image to a ComfyUI image tensor (1, Height, Width, Channels)."""
        image_np = np.array(image).astype(np.float32) / 255.0 # Convert to float32 (0-1 range)
        if image_np.ndim == 2: # Add channel dimension for grayscale
            image_np = np.expand_dims(image_np, axis=2)
        tensor = torch.from_numpy(image_np)
        return tensor.unsqueeze(0)  # Add batch dimension

    def _calculate_stats(self, pil_image: Image.Image):
        """Calculates mean luminance, contrast (stddev of luminance), and mean saturation for a PIL image."""
        img_lum_contrast = pil_image.convert("L")
        stat = ImageStat.Stat(img_lum_contrast)
        luminance = stat.mean[0]
        contrast = stat.stddev[0]

        img_hsv = pil_image.convert("HSV")
        s_channel = np.array(img_hsv)[:, :, 1] # Saturation channel
        saturation = np.mean(s_channel)

        return luminance, contrast, saturation

    def _match_histograms_numpy(self, source_np: np.ndarray, reference_np: np.ndarray) -> np.ndarray:
        """
        Matches the histogram of a source image to a reference image on a per-channel basis using NumPy.
        This alters the color distribution of the source to mimic the reference.
        """
        matched_channels = []
        for i in range(source_np.shape[2]):  # Iterate through R, G, B (or other) channels
            source_channel = source_np[:, :, i]
            ref_channel = reference_np[:, :, i]

            source_values, bin_idx, source_counts = np.unique(source_channel, return_inverse=True, return_counts=True)
            ref_values, ref_counts = np.unique(ref_channel, return_counts=True)

            source_cdf = np.cumsum(source_counts).astype(np.float64) / source_channel.size
            ref_cdf = np.cumsum(ref_counts).astype(np.float64) / ref_channel.size

            # Interpolate to map source CDF to reference pixel values
            interpolated_values = np.interp(source_cdf, ref_cdf, ref_values)

            matched_channel = interpolated_values[bin_idx].reshape(source_channel.shape)
            matched_channels.append(matched_channel)

        matched_np = np.stack(matched_channels, axis=-1).astype(np.uint8)
        return matched_np

    def apply_color_match(self, image: torch.Tensor, reference_image: torch.Tensor,
                          match_color: bool, color_mix: float,
                          match_saturation: bool, saturation_mix: float,
                          match_contrast: bool, contrast_mix: float,
                          match_luminance: bool, luminance_mix: float,
                          mask: torch.Tensor = None):
        """
        Applies selected color matching operations from a reference image to a source image.
        Supports batch processing and optional masking.
        """
        batch_size_img = image.shape[0]
        batch_size_ref = reference_image.shape[0]

        # Broadcast the smaller batch to match the larger one for consistent processing.
        if batch_size_img > batch_size_ref:
            reference_image_b = reference_image.repeat(batch_size_img // batch_size_ref, 1, 1, 1)
            image_b = image
        elif batch_size_ref > batch_size_img:
            image_b = image.repeat(batch_size_ref // batch_size_img, 1, 1, 1)
            reference_image_b = reference_image
        else:
            image_b = image
            reference_image_b = reference_image

        batch_size = max(batch_size_img, batch_size_ref)
        
        # Repeat mask if its batch size is smaller than the image batch size.
        if mask is not None and mask.shape[0] < batch_size:
            mask = mask.repeat(batch_size // mask.shape[0], 1, 1)

        output_images = []

        for i in range(batch_size): # Process each image in the batch
            source_pil = self.tensor_to_pil(image_b[i]).convert("RGB")
            ref_pil = self.tensor_to_pil(reference_image_b[i]).convert("RGB")

            modified_pil = source_pil.copy()

            # 1. Overall Color Matching (Histogram Matching)
            if match_color and color_mix > 0:
                source_np = np.array(modified_pil)
                ref_np = np.array(ref_pil)
                color_matched_np = self._match_histograms_numpy(source_np, ref_np)
                color_matched_pil = Image.fromarray(color_matched_np, 'RGB')
                modified_pil = Image.blend(modified_pil, color_matched_pil, color_mix) # Blend with original based on mix factor

            # Calculate stats from the (potentially already color-matched) image and reference.
            src_lum, src_con, src_sat = self._calculate_stats(modified_pil)
            ref_lum, ref_con, ref_sat = self._calculate_stats(ref_pil)

            # 2. Saturation Matching
            if match_saturation and saturation_mix > 0:
                if src_sat > 1e-5:  # Avoid division by zero if source saturation is negligible
                    sat_factor = ref_sat / src_sat # Calculate factor to match reference saturation
                    enhancer = ImageEnhance.Color(modified_pil)
                    sat_adjusted_pil = enhancer.enhance(sat_factor)
                    modified_pil = Image.blend(modified_pil, sat_adjusted_pil, saturation_mix)

            # 3. Contrast Matching
            if match_contrast and contrast_mix > 0:
                if src_con > 1e-5:  # Avoid division by zero
                    con_factor = ref_con / src_con # Calculate factor to match reference contrast
                    enhancer = ImageEnhance.Contrast(modified_pil)
                    con_adjusted_pil = enhancer.enhance(con_factor)
                    modified_pil = Image.blend(modified_pil, con_adjusted_pil, contrast_mix)

            # 4. Luminance Matching
            if match_luminance and luminance_mix > 0:
                if src_lum > 1e-5:  # Avoid division by zero
                    lum_factor = ref_lum / src_lum # Calculate factor to match reference luminance
                    enhancer = ImageEnhance.Brightness(modified_pil)
                    lum_adjusted_pil = enhancer.enhance(lum_factor)
                    modified_pil = Image.blend(modified_pil, lum_adjusted_pil, luminance_mix)
            
            # 5. Apply Mask (if provided)
            if mask is not None:
                mask_pil = self.tensor_to_pil(mask[i]).convert("L")
                if mask_pil.size != source_pil.size: # Resize mask if necessary
                    mask_pil = mask_pil.resize(source_pil.size, Image.Resampling.LANCZOS)
                
                # Paste the original source image onto the modified image using an inverted mask.
                # This ensures that the effect is applied only to the unmasked (white) areas.
                final_pil_with_mask = modified_pil.copy()
                final_pil_with_mask.paste(source_pil, (0, 0), ImageOps.invert(mask_pil))
                modified_pil = final_pil_with_mask

            output_images.append(self.pil_to_tensor(modified_pil))
            
        final_tensor = torch.cat(output_images, dim=0) # Concatenate processed images back into a batch
        
        # Return the modified image and the original reference image (passthrough)
        return (final_tensor, reference_image,)