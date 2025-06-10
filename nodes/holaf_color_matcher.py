import torch
import numpy as np
from PIL import Image

# MODIFICATION: Import 'ColorMatcher' AND 'METHODS' directly from 'top_level.py'
# where they are both defined. This ensures the import is correct.
from .libs.color_matcher.top_level import ColorMatcher, METHODS

class HolafColorMatcher:
    """
    A node to transfer color characteristics from a reference image to a source image,
    using various established algorithms from the 'color-matcher' library.
    """
    # Expose the available methods from the library in the UI
    AVAILABLE_METHODS = list(METHODS)

    @classmethod
    def INPUT_TYPES(s):
        """
        Defines the input types for the node, including a dropdown for the method.
        """
        return {
            "required": {
                "image": ("IMAGE",),
                "reference_image": ("IMAGE",),
                "method": (s.AVAILABLE_METHODS, {"default": "hm-mkl-hm"}),
                 # We can add a strength/mix slider later if needed, for now we do a full transfer.
            },
        }

    RETURN_TYPES = ("IMAGE", "IMAGE",)
    RETURN_NAMES = ("modified_image", "reference_image",)
    FUNCTION = "apply_color_match"
    CATEGORY = "Holaf"

    def tensor_to_np_uint8(self, tensor: torch.Tensor) -> np.ndarray:
        """Converts a ComfyUI image tensor (B, H, W, C) to a NumPy array (H, W, C) with uint8 type."""
        if not isinstance(tensor, torch.Tensor):
            raise TypeError(f"Input must be a torch.Tensor, got {type(tensor)}")
        
        # Process the first image in the batch
        img_t = tensor[0] 
        
        # Convert float (0-1) to uint8 (0-255)
        img_np = (img_t.cpu().numpy() * 255.0).astype(np.uint8)
        
        return img_np

    def np_to_tensor(self, img_np: np.ndarray) -> torch.Tensor:
        """Converts a NumPy image array (H, W, C) to a ComfyUI-compatible tensor."""
        # Convert to float (0-1) and create tensor
        img_t = torch.from_numpy(img_np.astype(np.float32) / 255.0)
        
        # Add batch dimension
        return img_t.unsqueeze(0)

    def apply_color_match(self, image: torch.Tensor, reference_image: torch.Tensor, method: str):
        """
        Applies the selected color matching algorithm.
        """
        # Ensure images have 3 channels (RGB) for the library to work correctly.
        source_np = self.tensor_to_np_uint8(image)[..., :3]
        ref_np = self.tensor_to_np_uint8(reference_image)[..., :3]

        # Use the color-matcher library
        try:
            # Instantiate the matcher with source, reference, and the chosen method
            cm = ColorMatcher(src=source_np, ref=ref_np, method=method)
            
            # Perform the color transfer
            result_np = cm.transfer()
            
            # The library can return float values, so we need to normalize and clip them
            # back to a valid uint8 range before converting back to a tensor.
            result_np = np.clip(result_np, 0, 255).astype(np.uint8)

        except Exception as e:
            print(f"[HolafColorMatcher] Error during color matching with method '{method}': {e}")
            # In case of an error, return the original image to avoid crashing the workflow
            result_np = source_np
        
        # Convert the result back to a tensor for ComfyUI
        result_tensor = self.np_to_tensor(result_np)
        
        return (result_tensor, reference_image,)