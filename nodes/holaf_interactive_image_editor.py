import torch
import numpy as np
import folder_paths
import os
from PIL import Image, ImageEnhance
import time
import hashlib

# ==================================================================================
# CONVENTION IMPORTANTE SUR LE FORMAT DES TENSEURS D'IMAGE DANS COMFYUI
# ... (commentaire complet sur NHWC comme dans la version précédente) ...
# ==================================================================================

class HolafInteractiveImageEditor:
    output_dir = folder_paths.get_temp_directory()
    type = "temp"
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            # print(f"[HolafEditor_PY INIT] Created temp directory: {output_dir}")
        except Exception as e:
            print(f"[HolafEditor_PY INIT] Error creating temp directory {output_dir}: {e}")

    # Ajout d'un constructeur pour initialiser last_processed_trigger
    def __init__(self):
        self.last_processed_trigger = -1
        self.last_image_hash_processed_for_downstream = "" # Pour suivre l'état de l'image réellement sortie
        self.last_params_hash_processed_for_downstream = "" # Pour suivre l'état des paramètres réellement sortis

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "brightness": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.01, "display": "slider"}),
                "contrast": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.01, "display": "slider"}),
                "saturation": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.01, "display": "slider"}),
                "red_mult": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.01, "display": "slider", "label": "R Multiply"}),
                "green_mult": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.01, "display": "slider", "label": "G Multiply"}),
                "blue_mult": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.01, "display": "slider", "label": "B Multiply"}),
            },
            "hidden": { # Ces entrées sont contrôlées par le JS
                "unique_id": "UNIQUE_ID", # Gardé pour l'unicité des fichiers temporaires
                "force_process_trigger": ("INT", {"default": 0, "forceInput": True, "widgetless": True}), # Incrémenté par le bouton JS
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE",)
    RETURN_NAMES = ("modified_image", "original_image",)
    FUNCTION = "process_images_with_apply_logic" # Renommé pour la clarté
    CATEGORY = "Holaf"

    @classmethod
    def IS_CHANGED(cls, image,
                   brightness: float, contrast: float, saturation: float, # Les sliders sont listés ici
                   red_mult: float, green_mult: float, blue_mult: float,
                   unique_id=None, force_process_trigger=0):

        # IS_CHANGED est appelé par ComfyUI pour savoir si le node doit être réexécuté
        # et si ses sorties ont potentiellement changé pour les nodes en aval.
        # Ici, on veut que le node soit réexécuté si l'image d'entrée change OU si le bouton "Apply" est cliqué.
        # Le changement des sliders seuls ne doit PAS rendre le node "changed" pour le downstream,
        # mais on a besoin de leurs valeurs actuelles pour la preview et pour le "Apply".

        # Générer un hash pour l'image d'entrée
        image_data_hash = ""
        if image is not None and hasattr(image, 'shape') and hasattr(image, 'device'):
            try:
                # S'assurer que le tenseur est sur CPU pour tobytes() et qu'il est contigu
                if image.device != torch.device('cpu'):
                    image_data_hash = hashlib.sha256(image.cpu().contiguous().numpy().tobytes()).hexdigest()
                else:
                    image_data_hash = hashlib.sha256(image.contiguous().numpy().tobytes()).hexdigest()
            except Exception as e:
                print(f"[HolafEditor_PY IS_CHANGED WARN] Could not hash input image: {e}")
                image_data_hash = str(time.time()) # Fallback pour assurer le changement

        # Les paramètres des sliders ne sont PAS inclus dans le hash de IS_CHANGED.
        # Seul force_process_trigger et l'image d'entrée déterminent si les sorties *pour le downstream* changent.
        # L'unique_id est là pour le node lui-même, pas pour la propagation.
        # On retourne le force_process_trigger pour qu'un clic sur le bouton "Apply" change la sortie.
        # print(f"[HolafEditor_PY IS_CHANGED] UID: {unique_id}, Image Hash: {image_data_hash}, Trigger: {force_process_trigger}")
        return f"{image_data_hash}_{force_process_trigger}"


    def _print_tensor_info(self, name, tensor_or_array, context_msg=""):
        # (content unchanged)
        prefix = f"[HolafEditor_PY TENSOR_DEBUG] ({context_msg}) {name}"
        if tensor_or_array is None: print(f"{prefix}: None"); return
        if isinstance(tensor_or_array, torch.Tensor):
            print(f"{prefix}: shape={tensor_or_array.shape}, dtype={tensor_or_array.dtype}, device={tensor_or_array.device}, min={tensor_or_array.min():.3f}, max={tensor_or_array.max():.3f}, is_contiguous={tensor_or_array.is_contiguous()}")
        elif isinstance(tensor_or_array, np.ndarray):
            print(f"{prefix} (numpy): shape={tensor_or_array.shape}, dtype={tensor_or_array.dtype}, min={tensor_or_array.min():.3f}, max={tensor_or_array.max():.3f}")
        elif isinstance(tensor_or_array, Image.Image):
            print(f"{prefix} (PIL): size={tensor_or_array.size}, mode={tensor_or_array.mode}")
        else: print(f"{prefix}: type={type(tensor_or_array)}")


    def _convert_tensor_nhwc_to_pil(self, tensor_nhwc, context_msg=""):
        # (content unchanged)
        if tensor_nhwc is None or tensor_nhwc.nelement() == 0: return None, "Input tensor NHWC None/empty"
        if not tensor_nhwc.is_contiguous(): tensor_nhwc = tensor_nhwc.contiguous()
        image_hwc_float = tensor_nhwc[0].cpu()
        numpy_hwc_uint8 = np.clip(image_hwc_float.numpy() * 255.0, 0, 255).astype(np.uint8)
        try:
            channels = numpy_hwc_uint8.shape[-1] if numpy_hwc_uint8.ndim == 3 else 1
            if channels == 1:
                 pil_image = Image.fromarray(numpy_hwc_uint8.squeeze(axis=-1) if numpy_hwc_uint8.ndim == 3 else numpy_hwc_uint8, mode='L')
            elif channels == 3:
                pil_image = Image.fromarray(numpy_hwc_uint8, mode='RGB')
            elif channels == 4:
                 pil_image = Image.fromarray(numpy_hwc_uint8, mode='RGBA')
            else:
                 return None, f"Unsupported number of channels ({channels}) in tensor for PIL conversion."
            return pil_image, None
        except Exception as e:
            self._print_tensor_info("numpy_hwc_uint8 AT ERROR in _convert_tensor_nhwc_to_pil", numpy_hwc_uint8, context_msg + " ERROR")
            print(f"[HolafEditor_PY ERROR] _convert_tensor_nhwc_to_pil failed for {context_msg}: {e}")
            return None, f"PIL creation error from NHWC tensor: {e}"

    def _convert_pil_to_tensor_nhwc(self, pil_image, target_device, original_nhwc_shape):
        # (content unchanged)
        if pil_image is None: return None, "PIL image is None"
        num_target_channels = original_nhwc_shape[-1]
        converted_pil_image = pil_image
        target_mode = None
        if num_target_channels == 1: target_mode = 'L'
        elif num_target_channels == 3: target_mode = 'RGB'
        elif num_target_channels == 4: target_mode = 'RGBA'
        if target_mode and pil_image.mode != target_mode:
            try:
                if target_mode == 'RGB' and pil_image.mode == 'RGBA':
                     converted_pil_image = pil_image.convert('RGB')
                elif pil_image.mode != target_mode:
                     converted_pil_image = pil_image.convert(target_mode)
            except Exception as e:
                 print(f"[HolafEditor_PY ERROR] _convert_pil_to_tensor_nhwc mode conversion failed: {e}")
                 return None, f"Error converting PIL mode from {pil_image.mode} to {target_mode}: {e}"
        img_np_hwc_float = np.array(converted_pil_image).astype(np.float32) / 255.0
        if converted_pil_image.mode == 'L' and img_np_hwc_float.ndim == 2:
            img_np_hwc_float = np.expand_dims(img_np_hwc_float, axis=-1)
        if img_np_hwc_float.ndim != 3 or img_np_hwc_float.shape[-1] != num_target_channels:
             print(f"[HolafEditor_PY ERROR] _convert_pil_to_tensor_nhwc channel mismatch. Numpy shape {img_np_hwc_float.shape}, target channels {num_target_channels}.")
             return None, f"Channel mismatch after PIL conversion. Numpy shape {img_np_hwc_float.shape} doesn't match target channels {num_target_channels}."
        tensor_hwc = torch.from_numpy(img_np_hwc_float)
        tensor_nhwc = tensor_hwc.unsqueeze(0).to(target_device)
        if tensor_nhwc.shape[1:3] != original_nhwc_shape[1:3]:
            print(f"[HolafEditor_PY ERROR] _convert_pil_to_tensor_nhwc spatial dim mismatch. Result: {tensor_nhwc.shape[1:3]}, Original: {original_nhwc_shape[1:3]}")
            return None, f"Spatial dimension mismatch. PIL conversion resulted in H,W {tensor_nhwc.shape[1:3]}, target original H,W was {original_nhwc_shape[1:3]}"
        return tensor_nhwc.contiguous(), None

    def save_image_and_get_info(self, tensor_nhwc, base_filename, unique_id_str=""):
        # print(f"[HolafEditor_PY DEBUG] save_image_and_get_info called for: {base_filename}, UID: {unique_id_str}")
        pil_img, error_msg = self._convert_tensor_nhwc_to_pil(tensor_nhwc.contiguous(), f"save_image_and_get_info ({base_filename})")
        if error_msg or pil_img is None:
            print(f"[HolafEditor_PY ERROR] save_image_and_get_info failed to convert tensor for '{base_filename}': {error_msg}")
            return {"filename": "", "subfolder": "", "type": self.type, "error": error_msg}

        if not hasattr(self, 'save_counter'): self.save_counter = int(time.time()) % 10000
        self.save_counter += 1
        safe_base_filename = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in base_filename)
        safe_unique_id_str = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in unique_id_str)
        filename = f"holaf_editor_{safe_base_filename}_{safe_unique_id_str}_{int(time.time()*1000)}_{self.save_counter:04d}.png"
        filepath = os.path.join(self.output_dir, filename)
        if not os.path.exists(self.output_dir):
             try: os.makedirs(self.output_dir)
             except Exception as e: return {"filename": "", "subfolder": "", "type": self.type, "error": f"Output directory missing/creation_failed: {e}"}
        try:
            pil_img.save(filepath, compress_level=1)
            # print(f"[HolafEditor_PY DEBUG] Image saved successfully: {filepath}")
            return {"filename": filename, "subfolder": "", "type": self.type}
        except Exception as e:
            print(f"[HolafEditor_PY ERROR] Error saving file '{filepath}': {e}")
            return {"filename": "", "subfolder": "", "type": self.type, "error": f"File save error: {e}"}

    def process_images_with_apply_logic(self, image: torch.Tensor,
                                        brightness: float = 1.0,
                                        contrast: float = 1.0,
                                        saturation: float = 1.0,
                                        red_mult: float = 1.0,
                                        green_mult: float = 1.0,
                                        blue_mult: float = 1.0,
                                        unique_id=None,
                                        force_process_trigger: int = 0):
        # print(f"--------------------------------------------------------------------------")
        # print(f"[HolafEditor_PY EXECUTE START] UID: {unique_id}. Trigger: {force_process_trigger}. Last Trigger: {self.last_processed_trigger}")
        # print(f"Params: B={brightness}, C={contrast}, S={saturation}, R={red_mult}, G={green_mult}, B={blue_mult}")

        unique_id_str = str(unique_id) if unique_id is not None else "unknownID"
        ui_info = {}

        # --- Normalisation de l'Entrée ---
        if image is None: image_tensor_list = []
        elif isinstance(image, torch.Tensor): image_tensor_list = [image]
        elif isinstance(image, list): image_tensor_list = image
        else:
            dummy = torch.zeros((1,64,64,3), dtype=torch.float32, device='cpu').contiguous()
            return {"ui": {"status":"Error: Unexpected input type"}, "result": (dummy.clone(), dummy.clone())}
        if not image_tensor_list or not isinstance(image_tensor_list[0], torch.Tensor) or image_tensor_list[0].nelement() == 0:
            dummy = torch.zeros((1,64,64,3), dtype=torch.float32, device='cpu').contiguous()
            return {"ui": {"status":"Error: Invalid or empty input tensor"}, "result": (dummy.clone(), dummy.clone())}

        input_tensor_master = image_tensor_list[0] # Garder une référence à l'image d'entrée réelle

        input_tensor = input_tensor_master.clone()
        # ... (le reste de la normalisation de input_tensor vers input_tensor_nhwc comme avant) ...
        input_tensor_nhwc = None
        if input_tensor.ndim == 4 and input_tensor.shape[3] in [1, 3, 4]: input_tensor_nhwc = input_tensor
        elif input_tensor.ndim == 4 and input_tensor.shape[1] in [1, 3, 4]: input_tensor_nhwc = input_tensor.permute(0, 2, 3, 1)
        elif input_tensor.ndim == 3 and input_tensor.shape[2] in [1, 3, 4]: input_tensor_nhwc = input_tensor.unsqueeze(0)
        elif input_tensor.ndim == 3 and input_tensor.shape[0] in [1, 3, 4]: input_tensor_nhwc = input_tensor.unsqueeze(0).permute(0, 2, 3, 1)
        else:
            dummy = torch.zeros((1,64,64,3),dtype=torch.float32, device=input_tensor.device if hasattr(input_tensor,'device') else 'cpu').contiguous()
            return {"ui": {"status":"Error: Input tensor format not recognized"}, "result": (dummy.clone(), dummy.clone())}
        if input_tensor_nhwc.shape[0] > 1: input_tensor_nhwc = input_tensor_nhwc[0].unsqueeze(0)
        if not input_tensor_nhwc.is_contiguous(): input_tensor_nhwc = input_tensor_nhwc.contiguous()
        if input_tensor_nhwc.dtype != torch.float32:
            if input_tensor_nhwc.is_floating_point(): input_tensor_nhwc = input_tensor_nhwc.to(torch.float32)
            elif input_tensor_nhwc.dtype == torch.uint8: input_tensor_nhwc = input_tensor_nhwc.to(torch.float32) / 255.0
            else:
                 try: input_tensor_nhwc = input_tensor_nhwc.to(torch.float32)
                 except Exception as e:
                     dummy = torch.zeros((1,64,64,3),dtype=torch.float32, device=input_tensor_nhwc.device if hasattr(input_tensor_nhwc,'device') else 'cpu').contiguous()
                     return {"ui": {"status":f"Error: Cannot convert input dtype {input_tensor_nhwc.dtype} to float32: {e}"}, "result": (dummy.clone(), dummy.clone())}
        input_tensor_nhwc = torch.clamp(input_tensor_nhwc, 0.0, 1.0)
        # --- Fin Normalisation ---

        original_tensor_for_preview = input_tensor_nhwc.clone() # C'est l'image qui entre dans les sliders pour la preview

        # --- Traitement de l'image pour la preview (toujours effectué) ---
        pil_img_orig_for_preview, error_msg = self._convert_tensor_nhwc_to_pil(original_tensor_for_preview, f"original_tensor_to_pil_for_preview UID {unique_id_str}")
        if error_msg or pil_img_orig_for_preview is None:
            # print(f"[HolafEditor_PY ERROR] EXECUTE failed converting original_for_preview to PIL: {error_msg}")
            return {"ui": {"status":f"Error converting original_for_preview to PIL: {error_msg}"}, "result": (original_tensor_for_preview.clone(), original_tensor_for_preview.clone())}

        pil_img_enhanced = pil_img_orig_for_preview
        try:
            # Appliquer les améliorations (brightness, contrast, etc.) sur pil_img_enhanced
            if brightness != 1.0:
                temp_img = pil_img_enhanced; enhancer = ImageEnhance.Brightness(temp_img.convert("RGB") if temp_img.mode not in ['L','RGB'] else temp_img); pil_img_enhanced = enhancer.enhance(brightness)
            if contrast != 1.0:
                temp_img = pil_img_enhanced; enhancer = ImageEnhance.Contrast(temp_img.convert("RGB") if temp_img.mode not in ['L','RGB'] else temp_img); pil_img_enhanced = enhancer.enhance(contrast)
            if saturation != 1.0:
                temp_img = pil_img_enhanced; original_mode_before_sat = temp_img.mode
                enhancer = ImageEnhance.Color(temp_img.convert("RGB") if temp_img.mode != 'RGB' else temp_img); pil_img_enhanced = enhancer.enhance(saturation)
            if red_mult != 1.0 or green_mult != 1.0 or blue_mult != 1.0:
                temp_img = pil_img_enhanced; alpha_channel = None
                if temp_img.mode == 'L': temp_img = temp_img.convert("RGB")
                elif temp_img.mode == 'RGBA': alpha_channel = temp_img.getchannel('A'); temp_img = temp_img.convert("RGB")
                elif temp_img.mode != 'RGB':
                    try: temp_img = temp_img.convert("RGB")
                    except Exception: raise StopIteration("Skipping RGB mult due to mode conversion error")
                if temp_img.mode == 'RGB': # Assurer que c'est RGB
                    np_img_float = np.array(temp_img).astype(np.float32) / 255.0
                    if np_img_float.ndim == 3 and np_img_float.shape[-1] == 3:
                        np_img_float[..., 0] *= red_mult; np_img_float[..., 1] *= green_mult; np_img_float[..., 2] *= blue_mult
                        np_img_uint8 = (np.clip(np_img_float, 0.0, 1.0) * 255.0).astype(np.uint8)
                        pil_img_enhanced = Image.fromarray(np_img_uint8, mode='RGB')
                        if alpha_channel: pil_img_enhanced.putalpha(alpha_channel)
        except StopIteration: pass
        except Exception as e:
            # print(f"[HolafEditor_PY ERROR] Error during image enhancement sequence: {e}")
            pil_img_enhanced = pil_img_orig_for_preview # Fallback
            ui_info["status_enhancement_error"] = f"Enhancement error: {e}"


        modified_tensor_for_preview, error_msg = self._convert_pil_to_tensor_nhwc(pil_img_enhanced, original_tensor_for_preview.device, original_tensor_for_preview.shape)
        if error_msg or modified_tensor_for_preview is None:
            # print(f"[HolafEditor_PY ERROR] Failed converting pil_img_enhanced to tensor: {error_msg}. Using original_for_preview.")
            modified_tensor_for_preview = original_tensor_for_preview.clone()
            ui_info["status_conversion_error"] = f"Conversion error: {error_msg}"
        # --- Fin traitement pour la preview ---

        # --- Sauvegarde pour l'UI JS (toujours basé sur les paramètres actuels) ---
        original_image_details_ui = self.save_image_and_get_info(original_tensor_for_preview, "uid_original", unique_id_str)
        modified_image_details_ui = self.save_image_and_get_info(modified_tensor_for_preview, "uid_preview_modified", unique_id_str)

        ui_info.update({f"original_{k}": v for k,v in original_image_details_ui.items() if k!="error"})
        ui_info.update({f"modified_{k}": v for k,v in modified_image_details_ui.items() if k!="error"})
        
        current_params_hash = hashlib.sha256(f"{brightness}_{contrast}_{saturation}_{red_mult}_{green_mult}_{blue_mult}".encode()).hexdigest()
        current_image_hash = ""
        if input_tensor_master is not None and hasattr(input_tensor_master, 'shape') and hasattr(input_tensor_master, 'device'):
             try:
                 if input_tensor_master.device != torch.device('cpu'):
                     current_image_hash = hashlib.sha256(input_tensor_master.cpu().contiguous().numpy().tobytes()).hexdigest()
                 else:
                     current_image_hash = hashlib.sha256(input_tensor_master.contiguous().numpy().tobytes()).hexdigest()
             except: pass


        # --- Logique pour déterminer la sortie réelle du node (pour le downstream) ---
        output_modified_image_downstream = None
        output_original_image_downstream = input_tensor_master.clone() # Toujours l'image d'entrée originale

        if self.last_processed_trigger != force_process_trigger:
            # Le bouton "Apply" a été cliqué (trigger a changé)
            # print(f"[HolafEditor_PY LOGIC] Apply button pressed. Trigger: {force_process_trigger} -> {self.last_processed_trigger}")
            output_modified_image_downstream = modified_tensor_for_preview.clone() # On utilise la version traitée avec les sliders actuels
            self.last_processed_trigger = force_process_trigger
            self.last_image_hash_processed_for_downstream = current_image_hash
            self.last_params_hash_processed_for_downstream = current_params_hash
            ui_info["status"] = "Applied. Outputting current edit."
            # print(f"[HolafEditor_PY LOGIC] Storing hash for applied: Img={current_image_hash}, Params={current_params_hash}")
        else:
            # Le bouton Apply n'a PAS été cliqué.
            # Si l'image d'ENTRÉE a changé, ou si les paramètres des SLIDERS ont changé
            # *depuis le dernier "Apply"*, on ne propage pas la modification.
            # On propage l'image originale ou la dernière image "Appliquée" si l'entrée et les params sont les mêmes qu'au dernier "Apply"
            if self.last_image_hash_processed_for_downstream == current_image_hash and \
               self.last_params_hash_processed_for_downstream == current_params_hash and \
               self.last_processed_trigger != -1 : # S'assurer qu'il y a eu au moins un "apply"
                # L'image d'entrée est la même que lors du dernier "Apply", et les sliders sont les mêmes
                # On peut donc repropager la même image modifiée (celle du dernier "Apply")
                # print(f"[HolafEditor_PY LOGIC] Passthrough: Input image and params match last Apply. Re-outputting last applied edit.")
                output_modified_image_downstream = modified_tensor_for_preview.clone() # Les params sont les mêmes, donc c'est la même image modifiée
                ui_info["status"] = "Re-outputting last applied edit (input/params unchanged)."
            else:
                # L'image d'entrée a changé, OU les sliders ont changé depuis le dernier "Apply", OU c'est la première exécution
                # print(f"[HolafEditor_PY LOGIC] Passthrough: Input image or params changed since last Apply, or first run. Outputting original.")
                # print(f"  Current Img Hash: {current_image_hash}, Last Applied Img Hash: {self.last_image_hash_processed_for_downstream}")
                # print(f"  Current Prm Hash: {current_params_hash}, Last Applied Prm Hash: {self.last_params_hash_processed_for_downstream}")
                output_modified_image_downstream = input_tensor_master.clone() # On renvoie l'originale non modifiée
                ui_info["status"] = "Previewing. Click 'Apply' in node to output edit."


        # print(f"[HolafEditor_PY RETURN DEBUG] Final ui_info to be returned:", ui_info)
        # print(f"[HolafEditor_PY EXECUTE END] UID: {unique_id}.")
        # print(f"--------------------------------------------------------------------------")
        return {"ui": ui_info, "result": (output_modified_image_downstream, output_original_image_downstream,)}