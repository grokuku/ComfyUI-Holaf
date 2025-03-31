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
                # Reordered inputs and updated defaults as requested
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
        """Converts a torch tensor (CHW or HWC) to a PIL Image."""
        if not isinstance(tensor, torch.Tensor):
             raise TypeError(f"Input must be a torch.Tensor, got {type(tensor)}")

        # Check if tensor is empty or has zero dimensions before squeezing
        if tensor.numel() == 0 or tensor.shape == torch.Size([]):
             # Handle empty tensor case: return a small black placeholder PIL image?
             # print("Warning: tensor_to_pil received an empty tensor.") # Removed debug
             return Image.new('RGB', (1, 1), color='black') # Or raise error

        image_np = tensor.squeeze().cpu().numpy()

        # If squeeze resulted in 0-dim array (e.g., from tensor with single value)
        if image_np.ndim == 0:
             # Treat as a single pixel value? Expand dims?
             # For now, let's assume it shouldn't happen for images and raise error or warning
             # print(f"Warning: tensor_to_pil resulted in 0-dim numpy array from tensor shape {tensor.shape}. Returning 1x1 black image.") # Removed debug
             return Image.new('RGB', (1, 1), color='black')


        # Handle CHW to HWC conversion
        if image_np.ndim == 3 and image_np.shape[0] in [1, 3, 4]:  # Check if first dim looks like channels
             image_np = np.transpose(image_np, (1, 2, 0))

        # Check dtype and scale/clip appropriately
        if image_np.dtype == np.float32 or image_np.dtype == np.float64:
            # Ensure float is in 0-1 range before scaling (important if input wasn't normalized)
            # Clipping might hide issues, but is safer than erroring
            image_np = np.clip(image_np, 0.0, 1.0)
            image_np = (image_np * 255)
        elif image_np.dtype == np.uint8:
            pass # Already in correct range 0-255
        else:
            # Handle other potential types or raise error
            # print(f"Warning: Unexpected numpy dtype {image_np.dtype} in tensor_to_pil. Attempting conversion via clip.") # Removed debug
            # Attempt to clip assuming it might be a larger int type or unnormalized float
            image_np = np.clip(image_np, 0, 255)

        # Ensure it's uint8 for PIL
        image_np = image_np.astype(np.uint8)

        # Handle potential single channel image (e.g., from mask) that became (H, W, 1) after transpose/logic
        # Or if original tensor was (B, H, W, 1) -> squeeze -> (H, W, 1)
        if image_np.ndim == 3 and image_np.shape[2] == 1:
             image_np = image_np.squeeze(axis=2) # Make it (H, W) for grayscale PIL

        # Final check for valid shape before creating image
        if image_np.ndim not in [2, 3]:
             # print(f"Error: Cannot create PIL image from numpy array with shape {image_np.shape}. Returning 1x1 black image.") # Removed debug
             return Image.new('RGB', (1, 1), color='black')
        if image_np.ndim == 3 and image_np.shape[2] not in [3, 4]:
             # print(f"Error: Cannot create PIL image from 3D numpy array with channel size {image_np.shape[2]}. Returning 1x1 black image.") # Removed debug
             # Could try converting to RGB if shape[2] == 1 was missed?
             return Image.new('RGB', (1, 1), color='black')


        try:
             return Image.fromarray(image_np)
        except Exception as e:
             # print(f"Error creating PIL Image from numpy array (shape: {image_np.shape}, dtype: {image_np.dtype}): {e}") # Removed debug
             # Return a placeholder or re-raise
             return Image.new('RGB', (1, 1), color='red') # Indicate error

    def pil_to_tensor(self, image):
        """Converts a PIL Image to a torch tensor (BCHW)."""
        image_np = np.array(image).astype(np.float32) / 255.0
        # If the input PIL image has an alpha channel, ensure the numpy array reflects that
        if image.mode == 'RGBA':
             if image_np.shape[-1] == 3: # If conversion somehow dropped alpha, add it back as opaque
                  alpha_channel = np.ones_like(image_np[..., :1])
                  image_np = np.concatenate((image_np, alpha_channel), axis=-1)
        elif image_np.ndim == 2: # Grayscale to RGB (implicitly no alpha)
            image_np = np.stack((image_np,)*3, axis=-1)

        tensor = torch.from_numpy(image_np)
        # Permute HWC to CHW; handle 4 channels (RGBA) correctly
        if tensor.ndim == 3:
             tensor = tensor.permute(2, 0, 1) # HWC to CHW
        return tensor.unsqueeze(0) # Add batch dimension

    def overlay(self, background_image, overlay_image, horizontal_align, vertical_align, offset_percent, size_percent, opacity, mask=None):
        # Ensure inputs are tensors
        if not isinstance(background_image, torch.Tensor):
            raise TypeError("background_image must be a torch.Tensor")
        if not isinstance(overlay_image, torch.Tensor):
            raise TypeError("overlay_image must be a torch.Tensor")

        # --- Debug Input ---
        # print(f"[HolafOverlayNode] Input background shape: {background_image.shape}, dtype: {background_image.dtype}") # Removed debug
        # print(f"[HolafOverlayNode] Input overlay shape: {overlay_image.shape}, dtype: {overlay_image.dtype}") # Removed debug
        # if background_image.ndim != 4: # Removed debug
        #      print(f"!!! Warning: background_image has unexpected ndim: {background_image.ndim}") # Removed debug
        # if overlay_image.ndim != 4: # Removed debug
        #      print(f"!!! Warning: overlay_image has unexpected ndim: {overlay_image.ndim}") # Removed debug
        # --- End Debug Input ---

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
            if mask is not None and mask.shape[0] == 1:
                 mask = mask.repeat(batch_size_bg, 1, 1) # Repeat mask too if needed
        elif batch_size_bg == 1 and batch_size_ov > 1:
             batch_size = batch_size_ov
             # Repeat background tensor to match overlay batch size
             background_image = background_image.repeat(batch_size_ov, 1, 1, 1)
        else:
            # If batch sizes mismatch and neither is 1, take the minimum
            # print(f"Warning: Mismatched batch sizes ({batch_size_bg} vs {batch_size_ov}). Using minimum size: {min(batch_size_bg, batch_size_ov)}") # Removed debug
            batch_size = min(batch_size_bg, batch_size_ov)

        results = []
        for i in range(batch_size):
            # Convert percentage inputs to float ratios for this iteration
            size = size_percent / 100.0
            offset = offset_percent / 100.0

            # Convert tensors to PIL Images for the current batch item
            bg_pil = self.tensor_to_pil(background_image[i])
            ov_pil = self.tensor_to_pil(overlay_image[i]) # This converts the i-th overlay tensor slice

            # --- Start of per-image processing ---
            bg_width, bg_height = bg_pil.size
            ov_orig_width, ov_orig_height = ov_pil.size # Get original overlay size from PIL

            # Check input tensor for alpha channel (assuming input is BHWC)
            # We check the specific slice corresponding to the loop iteration 'i'
            has_original_alpha = overlay_image.shape[-1] == 4

            # Create the BASE mask: Prioritize optional mask input, then check image alpha, then opaque.
            # This mask is still at the ORIGINAL size of the overlay.
            if mask is not None:
                 # Use the provided mask input
                 if mask.shape[0] != batch_size_ov and mask.shape[0] != 1:
                      raise ValueError(f"Mask batch size ({mask.shape[0]}) must match overlay batch size ({batch_size_ov}) or be 1.")
                 mask_idx = i if mask.shape[0] == batch_size_ov else 0
                 mask_tensor_slice = mask[mask_idx] # Get the relevant mask slice (H, W)
                 # Ensure mask tensor is float for proper scaling
                 mask_np_orig = mask_tensor_slice.cpu().float().numpy()
                 # Scale float tensor (0-1) to uint8 (0-255)
                 mask_np_scaled = (np.clip(mask_np_orig, 0.0, 1.0) * 255).astype(np.uint8)
                 base_mask_pil = Image.fromarray(mask_np_scaled, 'L')
                 # print(f"[HolafOverlayNode] Using provided mask input for overlay {i}.") # Removed debug
                 # Invert the mask from the input
                 base_mask_pil = ImageOps.invert(base_mask_pil)
                 # print(f"[HolafOverlayNode] Inverted provided mask.") # Removed debug
            elif has_original_alpha:
                # Fallback: Extract alpha from the *original* image tensor data slice
                alpha_tensor = overlay_image[i, :, :, 3] # Get alpha channel (H, W) from the i-th image in the batch
                # Ensure alpha tensor is float for proper scaling
                alpha_np_orig = alpha_tensor.cpu().float().numpy() # Use float()
                # Scale float tensor (0-1) to uint8 (0-255)
                alpha_np_scaled = (np.clip(alpha_np_orig, 0.0, 1.0) * 255).astype(np.uint8)
                # Ensure the numpy array is 2D (H, W) before creating PIL image
                if alpha_np_scaled.ndim == 3 and alpha_np_scaled.shape[-1] == 1:
                    alpha_np_scaled = alpha_np_scaled.squeeze(-1)
                elif alpha_np_scaled.ndim != 2:
                    raise ValueError(f"Unexpected alpha channel shape after processing: {alpha_np_scaled.shape}")
                base_mask_pil = Image.fromarray(alpha_np_scaled, 'L')
                # print(f"[HolafOverlayNode] Using original alpha channel from input tensor for overlay {i}.") # Removed debug
                # Invert the mask derived from image alpha
                base_mask_pil = ImageOps.invert(base_mask_pil)
                # print(f"[HolafOverlayNode] Inverted mask from image alpha.") # Removed debug
            else:
                # If no input alpha, create a fully opaque mask initially at original size
                # This mask should NOT be inverted, as it represents full opacity.
                base_mask_pil = Image.new('L', (ov_orig_width, ov_orig_height), 255)
                # print(f"[HolafOverlayNode] No original alpha channel found in input tensor for overlay {i}. Using opaque mask.") # Removed debug
            # print(f"[HolafOverlayNode] Base mask mode after creation: {base_mask_pil.mode}, size: {base_mask_pil.size}") # Removed debug

            # Calculate overlay TARGET size based on the largest dimension relative to background
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

            # Resize overlay AND the base mask if dimensions changed significantly
            needs_resize = abs(new_ov_width - ov_orig_width) > 1 or abs(new_ov_height - ov_orig_height) > 1
            if needs_resize:
                # print(f"[HolafOverlayNode] Resizing overlay {i} from {(ov_orig_width, ov_orig_height)} to {(new_ov_width, new_ov_height)}") # Removed debug
                # Ensure ov_pil has RGB channels before resizing if it was L mode
                if ov_pil.mode == 'L':
                     ov_pil = ov_pil.convert('RGB')
                # Ensure it has 3 channels for the color part before resizing
                if ov_pil.mode == 'RGBA':
                     ov_pil = ov_pil.convert('RGB') # Use only RGB for the color source

                ov_pil = ov_pil.resize((new_ov_width, new_ov_height), Image.Resampling.LANCZOS)
                base_mask_pil = base_mask_pil.resize((new_ov_width, new_ov_height), Image.Resampling.LANCZOS)

            # Apply opacity setting to the (potentially resized) base mask
            if opacity < 100:
                 opacity_factor = opacity / 100.0
                 mask_np = np.array(base_mask_pil).astype(np.float32)
                 mask_np *= opacity_factor
                 final_mask_pil = Image.fromarray(mask_np.clip(0, 255).astype(np.uint8), 'L')
                 # print(f"[HolafOverlayNode] Applied opacity {opacity}% to mask for overlay {i}.") # Removed debug
            else:
                 final_mask_pil = base_mask_pil # No opacity change needed, use the (potentially resized) base mask

            # Ensure ov_pil (the color source) is RGB before pasting
            if ov_pil.mode != 'RGB':
                 ov_pil = ov_pil.convert('RGB')

            # Calculate position based on alignment and offset using final overlay size
            min_bg_dim = min(bg_width, bg_height)
            offset_pixels = int(min_bg_dim * offset)

            # Calculate X position
            if horizontal_align == "left":
                paste_x = offset_pixels
            elif horizontal_align == "right":
                paste_x = bg_width - new_ov_width - offset_pixels
            else: # Default to left if invalid value somehow passed
                paste_x = offset_pixels

            # Calculate Y position
            if vertical_align == "top":
                paste_y = offset_pixels
            elif vertical_align == "bottom":
                paste_y = bg_height - new_ov_height - offset_pixels
            else: # Default to top if invalid value somehow passed
                paste_y = offset_pixels

            # Clamp positions to ensure overlay stays within background bounds
            max_paste_x = bg_width - new_ov_width
            max_paste_y = bg_height - new_ov_height
            paste_x = max(0, min(paste_x, max_paste_x))
            paste_y = max(0, min(paste_y, max_paste_y))

            # Create a copy of the background to paste onto
            result_pil = bg_pil.copy().convert("RGBA")

            # Paste the resized overlay (RGB part) onto the RGBA background using the resized final_mask_pil
            result_pil.paste(ov_pil, (paste_x, paste_y), final_mask_pil)

            # Result is already RGBA, keep it that way.

            # Convert back to tensor (pil_to_tensor handles RGBA implicitly if image_np has 4 channels)
            result_tensor_single = self.pil_to_tensor(result_pil)
            results.append(result_tensor_single)
            # --- End of per-image processing ---

        # Stack results into a single batch tensor
        if not results:
             # Handle case where batch size was 0 or loop didn't run
             # print("Warning: No images processed in HolafOverlayNode.") # Removed debug
             # Return original background or an empty tensor? Returning background might be safer.
             return (background_image,) # Or handle appropriately

        result_tensor_batch = torch.cat(results, dim=0)

        # --- Debug Output ---
        # print(f"[HolafOverlayNode] Output tensor shape (BCHW): {result_tensor_batch.shape}, dtype: {result_tensor_batch.dtype}") # Removed debug
        # --- End Debug Output ---

        # Convert final tensor from BCHW to BHWC for ComfyUI standard compatibility
        result_tensor_batch_bhwc = result_tensor_batch.permute(0, 2, 3, 1)
        # print(f"[HolafOverlayNode] Final Output tensor shape (BHWC): {result_tensor_batch_bhwc.shape}, dtype: {result_tensor_batch_bhwc.dtype}") # Removed debug

        return (result_tensor_batch_bhwc,)

# Node registration will be handled in __init__.py
