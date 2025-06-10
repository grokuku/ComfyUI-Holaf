import torch

class HolafMaskToBoolean:
    """
    A utility node that checks if an input mask is empty (all black).
    If the mask contains no white pixels (all values are 0), it outputs True.
    Otherwise, it outputs False. This is useful for creating a bypass signal
    for other nodes when a mask is not generated.
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("bypass",)
    FUNCTION = "check_mask_is_empty"
    CATEGORY = "Holaf/Masking"

    def check_mask_is_empty(self, mask: torch.Tensor):
        """
        Checks if the mask tensor is composed entirely of zeros.
        
        A mask is considered "empty" for bypass purposes if no part of it is active.
        In ComfyUI, an active mask area has values > 0 (typically 1.0 for white).
        An inactive mask area has a value of 0 (black).
        
        torch.all(mask == 0) efficiently checks if every element in the tensor is 0.
        .item() extracts the Python boolean value from the resulting tensor.
        """
        if mask is None or mask.numel() == 0:
            # If there's no mask or it's an empty tensor, consider it empty and bypass.
            return (True,)

        # If all pixels in the mask are 0, it's empty. Return True to bypass.
        is_empty = torch.all(mask == 0).item()
        
        return (is_empty,)

# This mapping is used by __init__.py to register the node with ComfyUI.
NODE_CLASS_MAPPINGS = {
  'HolafMaskToBoolean': HolafMaskToBoolean,
}