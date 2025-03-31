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
                "size": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.01}),
                "pos_x": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "pos_y": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
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

    def overlay(self, background_image, overlay_image, size, pos_x, pos_y, opacity):
        # Convert tensors to PIL Images
        # Assuming batch size is 1 for simplicity, take the first image
        bg_pil = self.tensor_to_pil(background_image[0])
        ov_pil = self.tensor_to_pil(overlay_image[0])

        # Ensure overlay has an alpha channel
        if ov_pil.mode != 'RGBA':
            ov_pil = ov_pil.convert('RGBA')

        # Apply opacity
        alpha = ov_pil.split()[3]
        alpha = ImageOps.colorize(alpha, (0, 0, 0, 0), (255, 255, 255, int(255 * (opacity / 100))))
        ov_pil.putalpha(alpha)

        # Calculate overlay size based on background width
        bg_width, bg_height = bg_pil.size
        ov_orig_width, ov_orig_height = ov_pil.size
        aspect_ratio = ov_orig_height / ov_orig_width

        new_ov_width = int(bg_width * size)
        new_ov_height = int(new_ov_width * aspect_ratio)

        # Ensure overlay doesn't exceed background dimensions if resized
        if new_ov_width > bg_width:
            new_ov_width = bg_width
            new_ov_height = int(new_ov_width * aspect_ratio)
        if new_ov_height > bg_height:
            new_ov_height = bg_height
            new_ov_width = int(new_ov_height / aspect_ratio)

        # Resize overlay if necessary
        if new_ov_width != ov_orig_width or new_ov_height != ov_orig_height:
             # Use LANCZOS for high-quality resizing
            ov_pil = ov_pil.resize((new_ov_width, new_ov_height), Image.Resampling.LANCZOS)


        # Calculate position
        # Position is relative to the top-left corner of the overlay
        max_x = bg_width - new_ov_width
        max_y = bg_height - new_ov_height

        paste_x = int(max_x * pos_x)
        paste_y = int(max_y * pos_y)

        # Ensure position is within bounds
        paste_x = max(0, min(paste_x, max_x))
        paste_y = max(0, min(paste_y, max_y))

        # Create a copy of the background to paste onto
        result_pil = bg_pil.copy().convert("RGBA") # Ensure background is RGBA for pasting with alpha

        # Paste the overlay using its alpha channel as a mask
        result_pil.paste(ov_pil, (paste_x, paste_y), ov_pil)

        # Convert back to RGB if the original background was RGB
        if bg_pil.mode == 'RGB':
            result_pil = result_pil.convert('RGB')

        # Convert back to tensor
        result_tensor = self.pil_to_tensor(result_pil)

        return (result_tensor,)

# Node registration will be handled in __init__.py
