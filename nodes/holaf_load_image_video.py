import os
import torch
import numpy as np
from PIL import Image, ImageOps
import cv2
import folder_paths

class HolafLoadImageVideo:
    """
    Node unifiée simplifiée.
    Charge tout média (Image ou Vidéo) via un seul point d'entrée.
    Nécessite le fichier JS associé pour lever le filtre de fichier dans le navigateur.
    """
    
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files.sort()
        
        return {
            "required": {
                # On renomme "image" en "media_file" pour la sémantique
                "media_file": (sorted(files), {"image_upload": True}),
            }
        }

    CATEGORY = "Holaf/IO"
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_media"
    OUTPUT_NODE = False

    def load_media(self, media_file):
        image_path = folder_paths.get_annotated_filepath(media_file)
        
        # Détection basique
        ext = os.path.splitext(image_path)[1].lower()
        VIDEO_EXTENSIONS = ['.mp4', '.webm', '.mkv', '.avi', '.mov', '.gif']
        
        if ext in VIDEO_EXTENSIONS:
            return self._load_video(image_path, media_file)
        else:
            return self._load_image_standard(image_path, media_file)

    def _load_image_standard(self, image_path, filename):
        try:
            i = Image.open(image_path)
        except OSError:
            raise ValueError(f"Le fichier '{filename}' n'est pas une image valide ou est corrompu.")

        i = ImageOps.exif_transpose(i)
        image = i.convert("RGB")
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
        
        if 'A' in i.getbands():
            mask = np.array(i.getchannel('A')).astype(np.float32) / 255.0
            mask = 1. - torch.from_numpy(mask)
        else:
            mask = torch.zeros((64,64), dtype=torch.float32, device="cpu")
            
        return {
            "ui": {"images": [{"filename": filename, "type": "input", "subfolder": ""}]},
            "result": (image, mask)
        }

    def _load_video(self, video_path, filename):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Impossible d'ouvrir la vidéo : {video_path}")

        frames = []
        preview_image = None
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # BGR -> RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                if preview_image is None:
                    preview_image = frame.copy()
                
                frame = frame.astype(np.float32) / 255.0
                frames.append(frame)
        finally:
            cap.release()

        if not frames:
            raise ValueError("Erreur : La vidéo semble vide ou illisible.")

        output_image = torch.from_numpy(np.stack(frames))
        b, h, w, c = output_image.shape
        output_mask = torch.zeros((b, h, w), dtype=torch.float32, device="cpu")

        if preview_image is not None:
            preview_filename = f"preview_{os.path.basename(filename)}.webp"
            self._save_preview(preview_image, preview_filename)
            
            return {
                "ui": {"images": [{"filename": preview_filename, "type": "temp", "subfolder": ""}]},
                "result": (output_image, output_mask)
            }
        
        return {"result": (output_image, output_mask)}

    def _save_preview(self, frame_np_uint8, filename):
        temp_dir = folder_paths.get_temp_directory()
        img = Image.fromarray(frame_np_uint8)
        img.save(os.path.join(temp_dir, filename))