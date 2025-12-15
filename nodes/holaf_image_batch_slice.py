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
        batch_count = images.shape[0]

        # 1. Clamp start_index to valid range
        if start_index < 0:
            start_index = 0
        
        if start_index >= batch_count:
            # If start is beyond the end, we just return the last image to avoid empty tensor errors
            start_index = batch_count - 1

        # 2. Logic for end_index (Inclusive)
        # If user wants frame 0 to 10, they expect 11 frames (0, 1... 10).
        # Python slice is exclusive [start:end], so we need end_index + 1.
        slice_end = end_index + 1

        # 3. Clamp slice_end
        if slice_end > batch_count:
            slice_end = batch_count
        
        # 4. Handle cases where End < Start
        if slice_end <= start_index:
            # Fallback: Return at least the start frame
            slice_end = start_index + 1

        # 5. Perform the slice
        # Tensor slicing: images[start:end]
        sliced_images = images[start_index:slice_end]
        
        # Debug info (optional, printed to console)
        print(f"[Holaf Image Batch Slice] Keeping frames {start_index} to {slice_end-1} (Total: {len(sliced_images)}) from original {batch_count}.")

        return (sliced_images,)