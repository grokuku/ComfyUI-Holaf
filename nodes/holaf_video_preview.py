import folder_paths
import os
import random
import numpy as np
import torch

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
        # Un identifiant unique pour éviter les collisions de fichiers temporaires
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

        # 1. Conversion Tensor -> Numpy
        img_array = (images.cpu().numpy() * 255.0).astype(np.uint8)
        batch_size, height, width, channels = img_array.shape

        # 2. Préparation du fichier temporaire
        # On génère un nom aléatoire pour ce run
        filename = f"{self.prefix}{random.randint(100000, 999999)}.mp4"
        file_path = os.path.join(self.output_dir, filename)

        # 3. Encodage Vidéo (H264 / MP4 pour compatibilité web maximale)
        try:
            container = av.open(file_path, mode='w')
            stream = container.add_stream('libx264', rate=fps)
            stream.width = width
            stream.height = height
            stream.pix_fmt = 'yuv420p' # Standard web
            stream.options = {'crf': str(quality), 'preset': 'fast'} # Fast pour ne pas ralentir le preview

            for i in range(batch_size):
                frame = av.VideoFrame.from_ndarray(img_array[i], format='rgb24')
                for packet in stream.encode(frame):
                    container.mux(packet)

            # Flush
            for packet in stream.encode():
                container.mux(packet)
            
            container.close()

        except Exception as e:
            print(f"⚠️ Holaf Video Preview Error: {e}")
            return (images,)

        # 4. Retour vers l'UI et Pass-through des images
        # On renvoie une structure spécifique que notre JS va intercepter
        preview_data = {
            "filename": filename,
            "subfolder": "",
            "type": self.type,
            "format": "mp4"
        }

        return {"ui": {"holaf_video": [preview_data]}, "result": (images,)}