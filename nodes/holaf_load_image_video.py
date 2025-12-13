import os
import torch
import numpy as np
from PIL import Image, ImageOps, ImageSequence
import cv2
import folder_paths

class HolafLoadImageVideo:
    """
    Node unifiée: Charge Images et Vidéos.
    - Preview animé pour les vidéos.
    - Supporte tous les formats via OpenCV et PIL.
    """
    
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        # On liste tout, sans filtre d'extension strict ici, on laisse le JS gérer le filtre visuel
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files.sort()
        
        return {
            "required": {
                "media_file": (sorted(files), {"image_upload": True}),
            },
            "optional": {
                 # Force rate permet de controler la vitesse de lecture si besoin, mais caché par défaut
                 "force_rate": ("INT", {"default": 0, "min": 0, "max": 60, "step": 1}),
            }
        }

    CATEGORY = "Holaf/IO"
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_media"
    OUTPUT_NODE = False

    def load_media(self, media_file, force_rate=0):
        image_path = folder_paths.get_annotated_filepath(media_file)
        
        # Validation du fichier
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Fichier introuvable: {image_path}")

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
            raise ValueError(f"Le fichier '{filename}' n'est pas une image valide.")

        i = ImageOps.exif_transpose(i)
        
        # Gestion GIF animé -> Séquence d'images
        if getattr(i, 'is_animated', False):
            frames = []
            for frame in ImageSequence.Iterator(i):
                frame = frame.convert("RGB")
                frame = np.array(frame).astype(np.float32) / 255.0
                frames.append(frame)
            image = torch.from_numpy(np.stack(frames))
            # Masque vide pour GIF
            mask = torch.zeros((len(frames), i.height, i.width), dtype=torch.float32, device="cpu")
        else:
            # Image statique
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
        # Utilisation de chemin absolu pour OpenCV
        abs_path = os.path.abspath(video_path)
        cap = cv2.VideoCapture(abs_path)
        
        if not cap.isOpened():
            raise ValueError(f"Impossible d'ouvrir la vidéo (codec ou chemin) : {abs_path}")

        frames = []
        preview_frames = []
        
        # Paramètres pour le preview animé (on ne garde pas toutes les frames pour l'UI si c'est trop lourd)
        total_frames_est = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        # On vise environ 50 frames max pour le preview pour garder l'UI fluide
        preview_step = max(1, total_frames_est // 50) 
        
        count = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # BGR -> RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Gestion du preview
                if count % preview_step == 0:
                    preview_frames.append(frame)

                # Normalisation pour le tenseur de sortie (Lourd)
                frame_norm = frame.astype(np.float32) / 255.0
                frames.append(frame_norm)
                
                count += 1
        finally:
            cap.release()

        if not frames:
            raise ValueError("Erreur : La vidéo semble vide ou illisible.")

        # Création du tenseur de sortie
        output_image = torch.from_numpy(np.stack(frames))
        b, h, w, c = output_image.shape
        output_mask = torch.zeros((b, h, w), dtype=torch.float32, device="cpu")

        # Génération du preview animé
        if preview_frames:
            preview_filename = f"preview_{os.path.basename(filename)}.webp"
            self._save_animated_preview(preview_frames, preview_filename)
            
            return {
                "ui": {"images": [{"filename": preview_filename, "type": "temp", "subfolder": ""}]},
                "result": (output_image, output_mask)
            }
        
        return {"result": (output_image, output_mask)}

    def _save_animated_preview(self, frames_list_np, filename):
        """Sauvegarde un WebP animé dans le dossier temp"""
        temp_dir = folder_paths.get_temp_directory()
        save_path = os.path.join(temp_dir, filename)
        
        pil_frames = [Image.fromarray(f) for f in frames_list_np]
        
        # Sauvegarde en WebP animé (léger et supporté par Comfy)
        # Duration = ms par frame. 33ms ~ 30fps.
        pil_frames[0].save(
            save_path,
            format='WEBP',
            save_all=True,
            append_images=pil_frames[1:],
            duration=50, 
            loop=0,
            quality=80,
            method=4
        )