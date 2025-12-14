import os
import torch
import numpy as np
from PIL import Image, ImageOps, ImageSequence
import folder_paths
import av 

class HolafLoadImageVideo:
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        if not os.path.exists(input_dir):
            os.makedirs(input_dir, exist_ok=True)
            
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files.sort()
        
        return {
            "required": {
                "media_file": (files,), 
            }
        }

    CATEGORY = "Holaf/IO"
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_media"
    OUTPUT_NODE = False

    def load_media(self, media_file):
        image_path = folder_paths.get_annotated_filepath(media_file)
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Fichier introuvable : {image_path}")

        try:
            return self._load_image_pil(image_path, media_file)
        except Exception:
            try:
                return self._load_video_av(image_path, media_file)
            except Exception as e_av:
                raise ValueError(f"Impossible de charger '{media_file}'. Le format n'est supporté ni par PIL, ni par PyAV.\nErreur: {e_av}")

    def _load_image_pil(self, image_path, filename):
        i = Image.open(image_path)
        i = ImageOps.exif_transpose(i)
        
        if getattr(i, 'is_animated', False):
            frames = []
            masks = []
            for frame in ImageSequence.Iterator(i):
                frame = frame.convert("RGBA")
                frame_np = np.array(frame).astype(np.float32) / 255.0
                frames.append(frame_np[:, :, :3]) 
                masks.append(1.0 - frame_np[:, :, 3]) 
            
            image_tensor = torch.from_numpy(np.stack(frames))
            mask_tensor = torch.from_numpy(np.stack(masks))
        else:
            i = i.convert("RGBA")
            image_np = np.array(i).astype(np.float32) / 255.0
            image_tensor = torch.from_numpy(image_np[:, :, :3])[None,]
            mask_tensor = torch.from_numpy(1.0 - image_np[:, :, 3])[None,]

        # Modification : On ne retourne QUE le résultat pour éviter le double preview natif
        return {
            "result": (image_tensor, mask_tensor)
        }

    def _load_video_av(self, video_path, filename):
        container = av.open(video_path)
        stream = container.streams.video[0]
        
        frames = []
        masks = []
        
        for frame in container.decode(stream):
            img_np = frame.to_ndarray(format='rgba').astype(np.float32) / 255.0
            frames.append(img_np[:, :, :3])
            masks.append(1.0 - img_np[:, :, 3])

        container.close()

        if not frames:
            raise ValueError(f"Vidéo lue mais aucune frame récupérée.")

        image_tensor = torch.from_numpy(np.stack(frames))
        mask_tensor = torch.from_numpy(np.stack(masks))
        
        # Modification : On ne retourne QUE le résultat pour éviter le double preview natif
        return {
            "result": (image_tensor, mask_tensor)
        }