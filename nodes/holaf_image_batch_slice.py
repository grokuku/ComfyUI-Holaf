import torch

class HolafImageBatchSlice:
    """
    Node to select a specific range of images (frames) from a batch.
    Useful for cutting video sequences loaded as image batches.
    """
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "start_index": ("INT", {
                    "default": 0, 
                    "min": 0, 
                    "max": 100000, 
                    "step": 1,
                    "display": "number" 
                }),
                "end_index": ("INT", {
                    "default": 10, 
                    "min": 0, 
                    "max": 100000, 
                    "step": 1,
                    "display": "number"
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("IMAGE",)
    FUNCTION = "slice_batch"
    CATEGORY = "Holaf/Image"

    def slice_batch(self, images, start_index, end_index):
        # images shape is [batch_size, height, width, channels]
        
        # 1. Clamp start_index to 0
        if start_index < 0:
            start_index = 0
            
        # 2. Logic for end_index (Inclusive)
        # Python slice is exclusive [start:end], so we need end_index + 1.
        slice_end = end_index + 1

        # 3. Perform the slice
        # PyTorch handles cases where slice_end <= start_index gracefully:
        # it returns an empty tensor of shape [0, H, W, C].
        sliced_images = images[start_index:slice_end]
        
        # Debug info
        print(f"[Holaf Image Batch Slice] Request: {start_index} to {end_index}. Output count: {sliced_images.shape[0]}")

        return (sliced_images,)