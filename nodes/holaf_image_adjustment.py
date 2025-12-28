import torch

class HolafImageAdjustment:
    """
    Adjusts Brightness, Contrast, and Saturation of an image using pure PyTorch operations.
    Performance optimized (no PIL conversion).
    """
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "brightness": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.05}),
                "contrast": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.05}),
                "saturation": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.05}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "adjust_image"
    CATEGORY = "Holaf/Image"

    def adjust_image(self, image, brightness, contrast, saturation):
        # Image comes in as [Batch, Height, Width, Channels]
        # Clone to ensure we don't modify the original tensor if used elsewhere
        img = image.clone()

        # 1. Apply Contrast
        # Formula: (color - middle_gray) * contrast + middle_gray
        # We assume 0.5 is middle gray for float images (0.0 - 1.0)
        if contrast != 1.0:
            img = (img - 0.5) * contrast + 0.5

        # 2. Apply Brightness
        # We use a multiplier (Gain/Exposure style) rather than an offset.
        # This keeps black as black (unless contrast moved it).
        if brightness != 1.0:
            img = img * brightness

        # 3. Apply Saturation
        if saturation != 1.0:
            # Calculate Luma (Grayscale) using Rec. 601 coefficients
            # 0.299 R + 0.587 G + 0.114 B
            # img[..., 0] is Red, 1 is Green, 2 is Blue
            luma = img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114
            
            # Expand luma dimensions to match image for broadcasting: [B, H, W] -> [B, H, W, 1]
            luma = luma.unsqueeze(-1)
            
            # Linear interpolation between Grayscale and Original
            img = luma + (img - luma) * saturation

        # Clamp values to valid 0.0 - 1.0 range to prevent artifacts
        img = torch.clamp(img, 0.0, 1.0)

        return (img,)