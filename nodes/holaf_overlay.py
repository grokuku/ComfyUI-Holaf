import torch
import numpy as np
from PIL import Image, ImageOps

class HolafOverlayNode:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "background_image": ("IMAGE",),
                "overlay_image": ("IMAGE",),
                "size_percent": ("INT", {"default": 100, "min": 1, "max": 1000, "step": 1}), # Renamed for clarity, allow > 100%
                "pos_x_percent": ("INT", {"default": 50, "min": 0, "max": 100, "step": 1}), # Renamed for clarity
                "pos_y_percent": ("INT", {"default": 50, "min": 0, "max": 100, "step": 1}), # Renamed for clarity
                "opacity": ("INT", {"default": 100, "min": 0, "max": 100, "step": 1}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "overlay"
    CATEGORY = "Holaf"

    def tensor_to_pil(self, tensor):
        """Converts a torch tensor (CHW or HWC) to a PIL Image."""
        image_np = tensor.squeeze().cpu().numpy()
        if image_np.ndim == 3 and image_np.shape[0] in [1, 3, 4]:  # CHW
             image_np = np.transpose(image_np, (1, 2, 0))
        image_np = (image_np * 255).astype(np.uint8)
        return Image.fromarray(image_np)

    def pil_to_tensor(self, image):
        """Converts a PIL Image to a torch tensor (BCHW)."""
        image_np = np.array(image).astype(np.float32) / 255.0
        if image_np.ndim == 2: # Grayscale to RGB
            image_np = np.stack((image_np,)*3, axis=-1)
        tensor = torch.from_numpy(image_np)
        if tensor.ndim == 3:
             tensor = tensor.permute(2, 0, 1) # HWC to CHW
        return tensor.unsqueeze(0) # Add batch dimension

    def overlay(self, background_image, overlay_image, size_percent, pos_x_percent, pos_y_percent, opacity):
        # Ensure inputs are tensors
        if not isinstance(background_image, torch.Tensor):
            raise TypeError("background_image must be a torch.Tensor")
        if not isinstance(overlay_image, torch.Tensor):
            raise TypeError("overlay_image must be a torch.Tensor")

        # Get batch sizes
        batch_size_bg = background_image.shape[0]
        batch_size_ov = overlay_image.shape[0]

        # Determine batch size (use smaller if different, or broadcast overlay if single)
        if batch_size_bg == batch_size_ov:
            batch_size = batch_size_bg
        elif batch_size_ov == 1 and batch_size_bg > 1:
            batch_size = batch_size_bg
            # Repeat overlay tensor to match background batch size
            overlay_image = overlay_image.repeat(batch_size_bg, 1, 1, 1)
        elif batch_size_bg == 1 and batch_size_ov > 1:
             batch_size = batch_size_ov
             # Repeat background tensor to match overlay batch size
             background_image = background_image.repeat(batch_size_ov, 1, 1, 1)
        else:
            # If batch sizes mismatch and neither is 1, take the minimum
            print(f"Warning: Mismatched batch sizes ({batch_size_bg} vs {batch_size_ov}). Using minimum size: {min(batch_size_bg, batch_size_ov)}")
            batch_size = min(batch_size_bg, batch_size_ov)

        results = []
        for i in range(batch_size):
            # Convert percentage inputs to float ratios for this iteration
            size = size_percent / 100.0
            pos_x = pos_x_percent / 100.0
            pos_y = pos_y_percent / 100.0

            # Convert tensors to PIL Images for the current batch item
            bg_pil = self.tensor_to_pil(background_image[i])
            ov_pil = self.tensor_to_pil(overlay_image[i])

            # --- Start of per-image processing ---
            # Ensure overlay has an alpha channel
            if ov_pil.mode != 'RGBA':
                ov_pil = ov_pil.convert('RGBA')

            # Apply opacity
            alpha = ov_pil.split()[3]
            alpha_np = np.array(alpha).astype(np.float32)
            alpha_np *= (opacity / 100.0)
            new_alpha = Image.fromarray(alpha_np.clip(0, 255).astype(np.uint8), 'L')
            ov_pil.putalpha(new_alpha)

            # Calculate overlay size based on the largest dimension relative to background
            bg_width, bg_height = bg_pil.size
            ov_orig_width, ov_orig_height = ov_pil.size

            target_bg_dim = max(bg_width, bg_height)
            target_ov_dim = int(target_bg_dim * size)

            ov_aspect_ratio = ov_orig_width / ov_orig_height if ov_orig_height != 0 else 1

            if ov_orig_width >= ov_orig_height:
                new_ov_width = target_ov_dim
                new_ov_height = int(new_ov_width / ov_aspect_ratio) if ov_aspect_ratio != 0 else target_ov_dim
            else:
                new_ov_height = target_ov_dim
                new_ov_width = int(new_ov_height * ov_aspect_ratio)

            # Ensure calculated dimensions are at least 1 pixel
            new_ov_width = max(1, new_ov_width)
            new_ov_height = max(1, new_ov_height)

            # Clamp dimensions if they exceed background size
            new_ov_width = min(new_ov_width, bg_width)
            new_ov_height = min(new_ov_height, bg_height)

            # Resize overlay only if dimensions changed significantly
            if abs(new_ov_width - ov_orig_width) > 1 or abs(new_ov_height - ov_orig_height) > 1:
                ov_pil = ov_pil.resize((new_ov_width, new_ov_height), Image.Resampling.LANCZOS)
            else: # Update dimensions if resize didn't happen but clamping might have
                new_ov_width = ov_orig_width if new_ov_width == 0 else new_ov_width # Use original if calc resulted in 0
                new_ov_height = ov_orig_height if new_ov_height == 0 else new_ov_height

            # Calculate position
            max_x = bg_width - new_ov_width
            max_y = bg_height - new_ov_height
            paste_x = int(max_x * pos_x)
            paste_y = int(max_y * pos_y)
            paste_x = max(0, min(paste_x, max_x))
            paste_y = max(0, min(paste_y, max_y))

            # Create a copy of the background to paste onto
            result_pil = bg_pil.copy().convert("RGBA")

            # Paste the overlay using its alpha channel as a mask
            result_pil.paste(ov_pil, (paste_x, paste_y), ov_pil)

            # Ensure final result is RGB before converting to tensor for compatibility
            result_pil = result_pil.convert('RGB')

            # Convert back to tensor and add to results list
            result_tensor_single = self.pil_to_tensor(result_pil)
            results.append(result_tensor_single)
            # --- End of per-image processing ---

        # Stack results into a single batch tensor
        if not results:
             # Handle case where batch size was 0 or loop didn't run
             print("Warning: No images processed in HolafOverlayNode.")
             # Return original background or an empty tensor? Returning background might be safer.
             return (background_image,) # Or handle appropriately

        result_tensor_batch = torch.cat(results, dim=0)
        return (result_tensor_batch,)

# Node registration will be handled in __init__.py
