import os
import uuid
import numpy as np
import torch
import folder_paths

# Gestion de la dépendance PyAV
try:
    import av
except ImportError:
    av = None

class HolafVideoPreview:
    """
    Node to preview a sequence of images as a video within ComfyUI
    without saving it permanently to the output folder.
    """
    def __init__(self):
        self.output_dir = folder_paths.get_temp_directory()
        self.type = "temp"
        self.prefix = "holaf_preview_"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "fps": ("INT", {"default": 24, "min": 1, "max": 120, "step": 1}),
                "quality": ("INT", {"default": 20, "min": 0, "max": 63, "step": 1, "tooltip": "CRF (Lower is better quality)"}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "preview_video"
    OUTPUT_NODE = True
    CATEGORY = "Holaf/View"

    def preview_video(self, images, fps, quality):
        if av is None:
            print("⚠️ Holaf Video Preview: PyAV ('av') not installed. Passing through images without preview.")
            return (images,)

        # PyTorch SIMD conversion (avoids numpy float64 promotion)
        img_array = images.cpu().float().mul(255).clamp(0, 255).byte().numpy()
        batch_size, height, width, channels = img_array.shape

        # Unique filename to avoid collisions
        filename = f"{self.prefix}{uuid.uuid4().hex[:12]}.mp4"
        file_path = os.path.join(self.output_dir, filename)

        try:
            container = av.open(file_path, mode='w')
            stream = container.add_stream('libx264', rate=fps)
            stream.width = width
            stream.height = height
            stream.pix_fmt = 'yuv420p'
            stream.options = {'crf': str(quality), 'preset': 'fast'}

            for i in range(batch_size):
                frame = av.VideoFrame.from_ndarray(img_array[i], format='rgb24')
                for packet in stream.encode(frame):
                    container.mux(packet)

            for packet in stream.encode():
                container.mux(packet)

            container.close()

        except Exception as e:
            print(f"⚠️ Holaf Video Preview Error: {e}")
            return (images,)

        preview_data = {
            "filename": filename,
            "subfolder": "",
            "type": self.type,
            "format": "mp4"
        }

        return {"ui": {"holaf_video": [preview_data]}, "result": (images,)}