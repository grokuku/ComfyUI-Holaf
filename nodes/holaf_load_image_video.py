import os
import torch
import numpy as np
from PIL import Image, ImageOps, ImageSequence
import cv2
import folder_paths

class HolafLoadImageVideo:
    """
    Node unifiée : Charge Images et Vidéos.
    - Force le preview animé (WebP léger).
    - Supporte MP4, WEBM, GIF, etc.
    """
    
    @classmethod
    def INPUT_TYPES(s):
        input_dir = folder_paths.get_input_directory()
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        files.sort()
        
        return {
            "required": {
                "media_file": (sorted(files), {"image_upload": True}),
            }
        }

    CATEGORY = "Holaf/IO"
    RETURN_TYPES = ("IMAGE", "MASK")
    FUNCTION = "load_media"
    OUTPUT_NODE = False

    def load_media(self, media_file):
        image_path = folder_paths.get_annotated_filepath(media_file)
        
        # LOG DE DEBUG
        print(f"🎥 HolafLoad: Tentative de chargement de {media_file}")
        print(f"   -> Chemin absolu : {image_path}")
        
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
        
        # Gestion GIF animé
        if getattr(i, 'is_animated', False):
            frames = []
            for frame in ImageSequence.Iterator(i):
                frame = frame.convert("RGB")
                frame = np.array(frame).astype(np.float32) / 255.0
                frames.append(frame)
            image = torch.from_numpy(np.stack(frames))
            mask = torch.zeros((len(frames), i.height, i.width), dtype=torch.float32, device="cpu")
        else:
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
            # Fallback : parfois OpenCV a besoin du chemin absolu normalisé
            abs_path = os.path.abspath(video_path)
            cap = cv2.VideoCapture(abs_path)
            if not cap.isOpened():
                raise ValueError(f"CRITIQUE: Impossible d'ouvrir la vidéo. Vérifiez les codecs ou le chemin.\nPath: {video_path}")

        frames = []
        preview_frames = []
        
        # On limite le nombre de frames pour le PREVIEW seulement (pour qu'il reste fluide)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0: total_frames = 100 # Valeur par défaut si lecture impossible
        
        # On garde max 60 frames pour le preview
        preview_step = max(1, total_frames // 60)
        
        count = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # BGR -> RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Ajout au preview (redimensionné plus tard)
                if count % preview_step == 0:
                    preview_frames.append(frame)

                # Ajout au résultat final (Pleine résolution)
                frame_norm = frame.astype(np.float32) / 255.0
                frames.append(frame_norm)
                
                count += 1
        finally:
            cap.release()

        if not frames:
            raise ValueError("La vidéo a été ouverte mais aucune frame n'a été lue.")

        print(f"✅ Vidéo chargée: {len(frames)} frames.")

        output_image = torch.from_numpy(np.stack(frames))
        b, h, w, c = output_image.shape
        output_mask = torch.zeros((b, h, w), dtype=torch.float32, device="cpu")

        # Génération du preview animé OPTIMISÉ
        if preview_frames:
            preview_filename = f"preview_{os.path.basename(filename)}.webp"
            self._save_animated_preview(preview_frames, preview_filename)
            
            return {
                "ui": {"images": [{"filename": preview_filename, "type": "temp", "subfolder": ""}]},
                "result": (output_image, output_mask)
            }
        
        return {"result": (output_image, output_mask)}

    def _save_animated_preview(self, frames_list_np, filename, max_size=512):
        """Sauvegarde un WebP animé REDIMENSIONNÉ (Thumbnail)"""
        temp_dir = folder_paths.get_temp_directory()
        save_path = os.path.join(temp_dir, filename)
        
        pil_frames = []
        for f in frames_list_np:
            img = Image.fromarray(f)
            # Redimensionnement proportionnel pour le preview
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            pil_frames.append(img)
        
        # Sauvegarde (duration=33ms => ~30fps)
        pil_frames[0].save(
            save_path,
            format='WEBP',
            save_all=True,
            append_images=pil_frames[1:],
            duration=33, 
            loop=0,
            quality=75,
            method=4
        )