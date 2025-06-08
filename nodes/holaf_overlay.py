import torch
import numpy as np
from PIL import Image, ImageOps

class HolafOverlayNode:
    """
    Overlays one image onto another with controls for size, position, opacity,
    and masking. Supports batch operations.
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "background_image": ("IMAGE",),
                "overlay_image": ("IMAGE",),
                "vertical_align": (["top", "bottom"], {"default": "bottom"}),
                "horizontal_align": (["left", "right"], {"default": "left"}),
                "offset_percent": ("INT", {"default": 1, "min": 0, "max": 100, "step": 1}),
                "size_percent": ("INT", {"default": 5, "min": 1, "max": 1000, "step": 1}),
                "opacity": ("INT", {"default": 50, "min": 0, "max": 100, "step": 1}),
            },
            "optional": {
                 "mask": ("MASK",),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "overlay"
    CATEGORY = "Holaf"

    def tensor_to_pil(self, tensor):
        """A robust helper to convert a ComfyUI image tensor into a PIL Image for manipulation."""
        if not isinstance(tensor, torch.Tensor):
             raise TypeError(f"Input must be a torch.Tensor, got {type(tensor)}")
        if tensor.numel() == 0:
             return Image.new('RGB', (1, 1), color='black')

        image_np = tensor.squeeze().cpu().numpy()

        if image_np.ndim == 0:
             return Image.new('RGB', (1, 1), color='black')

        if image_np.ndim == 3 and image_np.shape[0] in [1, 3, 4]:
             image_np = np.transpose(image_np, (1, 2, 0)) # CHW to HWC

        if image_np.dtype in [np.float32, np.float64]:
            image_np = (np.clip(image_np, 0.0, 1.0) * 255)
        
        image_np = np.clip(image_np, 0, 255).astype(np.uint8)

        if image_np.ndim == 3 and image_np.shape[2] == 1:
             image_np = image_np.squeeze(axis=2)

        try:
             return Image.fromarray(image_np)
        except Exception as e:
             print(f"Error creating PIL Image from numpy array (shape: {image_np.shape}, dtype: {image_np.dtype}): {e}")
             return Image.new('RGB', (1, 1), color='red')

    def pil_to_tensor(self, image):
        """Converts a PIL Image to a batched tensor in BCHW format for processing."""
        image_np = np.array(image).astype(np.float32) / 255.0
        if image.mode == 'RGBA' and image_np.shape[-1] == 3:
             alpha_channel = np.ones_like(image_np[..., :1])
             image_np = np.concatenate((image_np, alpha_channel), axis=-1)
        elif image_np.ndim == 2:
            image_np = np.stack((image_np,)*3, axis=-1)

        tensor = torch.from_numpy(image_np)
        if tensor.ndim == 3:
             tensor = tensor.permute(2, 0, 1) # HWC to CHW
        return tensor.unsqueeze(0) # Add batch dimension -> BCHW

    def overlay(self, background_image, overlay_image, horizontal_align, vertical_align, offset_percent, size_percent, opacity, mask=None):
        if not isinstance(background_image, torch.Tensor) or not isinstance(overlay_image, torch.Tensor):
            raise TypeError("Inputs must be torch.Tensor")

        # --- Batch Handling ---
        # If one input has a batch size of 1, broadcast it to match the other.
        # This allows applying one overlay to multiple backgrounds, or vice-versa.
        batch_size_bg = background_image.shape[0]
        batch_size_ov = overlay_image.shape[0]
        batch_size = batch_size_bg

        if batch_size_bg != batch_size_ov:
            if batch_size_ov == 1 and batch_size_bg > 1:
                overlay_image = overlay_image.repeat(batch_size_bg, 1, 1, 1)
                if mask is not None and mask.shape[0] == 1:
                     mask = mask.repeat(batch_size_bg, 1, 1)
            elif batch_size_bg == 1 and batch_size_ov > 1:
                 background_image = background_image.repeat(batch_size_ov, 1, 1, 1)
                 batch_size = batch_size_ov
            else:
                 batch_size = min(batch_size_bg, batch_size_ov)

        results = []
        for i in range(batch_size):
            bg_pil = self.tensor_to_pil(background_image[i])
            ov_pil = self.tensor_to_pil(overlay_image[i])
            bg_width, bg_height = bg_pil.size
            ov_orig_width, ov_orig_height = ov_pil.size

            # --- Mask Creation ---
            # Determine the mask with a clear priority:
            # 1. Use the explicit `mask` input if provided.
            # 2. Else, use the alpha channel of the `overlay_image`.
            # 3. Else, create a fully opaque mask (the overlay will be a solid rectangle).
            # IMPORTANT: The mask is inverted. Black areas define where the overlay is applied.
            if mask is not None:
                 mask_tensor_slice = mask[i if mask.shape[0] == batch_size else 0]
                 mask_np_scaled = (np.clip(mask_tensor_slice.cpu().float().numpy(), 0.0, 1.0) * 255).astype(np.uint8)
                 base_mask_pil = Image.fromarray(mask_np_scaled, 'L')
                 base_mask_pil = ImageOps.invert(base_mask_pil)
            elif overlay_image.shape[-1] == 4:
                alpha_tensor = overlay_image[i, :, :, 3]
                alpha_np_scaled = (np.clip(alpha_tensor.cpu().float().numpy(), 0.0, 1.0) * 255).astype(np.uint8)
                base_mask_pil = Image.fromarray(alpha_np_scaled, 'L')
                base_mask_pil = ImageOps.invert(base_mask_pil)
            else:
                # Opaque mask is NOT inverted here; it's just a solid white area.
                base_mask_pil = Image.new('L', (ov_orig_width, ov_orig_height), 255)

            # --- Size Calculation ---
            # Overlay size is relative to the background's largest dimension.
            target_bg_dim = max(bg_width, bg_height)
            target_ov_dim = int(target_bg_dim * (size_percent / 100.0))
            ov_aspect_ratio = ov_orig_width / ov_orig_height if ov_orig_height != 0 else 1

            if ov_orig_width >= ov_orig_height:
                new_ov_width = target_ov_dim
                new_ov_height = int(new_ov_width / ov_aspect_ratio)
            else:
                new_ov_height = target_ov_dim
                new_ov_width = int(new_ov_height * ov_aspect_ratio)

            # Ensure new dimensions are valid and within background bounds.
            new_ov_width = min(max(1, new_ov_width), bg_width)
            new_ov_height = min(max(1, new_ov_height), bg_height)
            
            # Resize both the overlay and its mask to the new dimensions.
            ov_pil = ov_pil.convert('RGB').resize((new_ov_width, new_ov_height), Image.Resampling.LANCZOS)
            base_mask_pil = base_mask_pil.resize((new_ov_width, new_ov_height), Image.Resampling.LANCZOS)

            # --- Opacity and Positioning ---
            # Apply opacity directly to the mask before pasting.
            if opacity < 100:
                 mask_np = np.array(base_mask_pil).astype(np.float32) * (opacity / 100.0)
                 final_mask_pil = Image.fromarray(np.clip(mask_np, 0, 255).astype(np.uint8), 'L')
            else:
                 final_mask_pil = base_mask_pil

            # Position offset is relative to the background's smallest dimension.
            offset_pixels = int(min(bg_width, bg_height) * (offset_percent / 100.0))
            paste_x = offset_pixels if horizontal_align == "left" else bg_width - new_ov_width - offset_pixels
            paste_y = offset_pixels if vertical_align == "top" else bg_height - new_ov_height - offset_pixels
            
            # Clamp coordinates to ensure the overlay is fully visible.
            paste_x = max(0, min(paste_x, bg_width - new_ov_width))
            paste_y = max(0, min(paste_y, bg_height - new_ov_height))
            
            # --- Compositing ---
            # Paste the overlay onto a copy of the background using the final mask.
            result_pil = bg_pil.copy().convert("RGBA")
            result_pil.paste(ov_pil, (paste_x, paste_y), final_mask_pil)
            
            results.append(self.pil_to_tensor(result_pil))

        if not results:
             return (background_image,)

        # Stack the list of processed tensors into a single batch tensor.
        result_tensor_batch = torch.cat(results, dim=0)
        
        # Convert final tensor from processing format (BCHW) to ComfyUI's standard image format (BHWC).
        result_tensor_batch_bhwc = result_tensor_batch.permute(0, 2, 3, 1)

        return (result_tensor_batch_bhwc,)