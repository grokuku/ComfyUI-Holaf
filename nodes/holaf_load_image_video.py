import os
import torch
import numpy as np
from PIL import Image, ImageOps
import cv2
import folder_paths

class HolafLoadImageVideo:
    """
    Node unifiée pour charger des images ou des vidéos.
    Gère: jpg, png, webp, webm, gif, mp4, etc.
    Sortie: Image unique ou Batch d'images.
    """
    
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files.sort()
        
        return {
            "required": {
                "image": (sorted(files), {"image_upload": True}),
            },
            "optional": {
                "start_frame": ("INT", {"default": 0, "min": 0, "step": 1, "display": "number"}),
                "frame_limit": ("INT", {"default": 0, "min": 0, "step": 1, "display": "number", "tooltip": "0 = no limit"}),
            }
        }

    CATEGORY = "Holaf/IO"
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_media"
    OUTPUT_NODE = False

    def load_media(self, image, start_frame=0, frame_limit=0):
        image_path = folder_paths.get_annotated_filepath(image)
        
        # Détection basique du type de fichier
        ext = os.path.splitext(image_path)[1].lower()
        VIDEO_EXTENSIONS = ['.mp4', '.webm', '.mkv', '.avi', '.mov', '.gif']
        
        if ext in VIDEO_EXTENSIONS:
            return self._load_video(image_path, start_frame, frame_limit, image)
        else:
            return self._load_image_standard(image_path, image)

    def _load_image_standard(self, image_path, filename):
        i = Image.open(image_path)
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

    def _load_video(self, video_path, start_frame, frame_limit, filename):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Impossible d'ouvrir la vidéo : {video_path}")

        frames = []
        
        # Positionnement rapide au début si nécessaire
        if start_frame > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
        current_count = 0
        preview_image = None
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Vérification limite
                if frame_limit > 0 and current_count >= frame_limit:
                    break
                
                # BGR -> RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Sauvegarde de la 1ère frame lue pour le preview
                if preview_image is None:
                    preview_image = frame.copy()
                
                # Normalisation
                frame = frame.astype(np.float32) / 255.0
                frames.append(frame)
                current_count += 1
        finally:
            cap.release()

        if not frames:
            raise ValueError("Aucune frame chargée. Vérifiez le fichier ou start_frame.")

        output_image = torch.from_numpy(np.stack(frames))
        
        # Génération d'un masque vide (tout visible)
        b, h, w, c = output_image.shape
        output_mask = torch.zeros((b, h, w), dtype=torch.float32, device="cpu")

        # Gestion Preview UI
        if preview_image is not None:
            # On génère un nom unique pour le preview dans temp
            preview_filename = f"preview_{os.path.basename(filename)}.webp"
            self._save_preview(preview_image, preview_filename)
            
            return {
                "ui": {"images": [{"filename": preview_filename, "type": "temp", "subfolder": ""}]},
                "result": (output_image, output_mask)
            }
        
        # Fallback si pas de preview
        return {"result": (output_image, output_mask)}

    def _save_preview(self, frame_np_uint8, filename):
        """Sauvegarde une frame (ndarray uint8) dans le dossier temp de ComfyUI"""
        temp_dir = folder_paths.get_temp_directory()
        img = Image.fromarray(frame_np_uint8)
        img.save(os.path.join(temp_dir, filename))