# Copyright (C) 2025 Holaf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import torch
import numpy as np
import folder_paths
import os
from PIL import Image, ImageEnhance
import time
import hashlib

class HolafInteractiveImageEditor:
    output_dir = folder_paths.get_temp_directory()
    type = "temp"
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
        except Exception as e:
            print(f"[HolafEditor] Error creating temp directory {output_dir}: {e}")

    def __init__(self):
        """Initializes the node's state."""
        # Tracks the trigger value from the UI button to detect clicks.
        self.last_processed_trigger = -1
        # Stores a hash of the image that was last sent to downstream nodes.
        self.last_image_hash_processed_for_downstream = ""
        # Stores a hash of the parameters that were last sent to downstream nodes.
        self.last_params_hash_processed_for_downstream = ""

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
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "force_process_trigger": ("INT", {"default": 0, "forceInput": True, "widgetless": True}),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE",)
    RETURN_NAMES = ("modified_image", "original_image",)
    FUNCTION = "process_images_with_apply_logic"
    CATEGORY = "Holaf"

    @classmethod
    def IS_CHANGED(cls, image,
                   brightness: float, contrast: float, saturation: float,
                   red_mult: float, green_mult: float, blue_mult: float,
                   unique_id=None, force_process_trigger=0):
        """
        Determines if the node's output has changed.
        The node is considered "changed" for downstream execution only if the input image
        changes OR the "Apply" button is clicked (changing `force_process_trigger`).
        Slider adjustments alone do not trigger a change here, but the node still
        re-runs to update its internal preview.
        """
        image_data_hash = ""
        if image is not None and hasattr(image, 'shape') and hasattr(image, 'device'):
            try:
                # Ensure tensor is on CPU and contiguous for consistent hashing.
                img_cpu = image.cpu().contiguous()
                image_data_hash = hashlib.sha256(img_cpu.numpy().tobytes()).hexdigest()
            except Exception as e:
                print(f"[HolafEditor] IS_CHANGED warning: Could not hash input image: {e}")
                image_data_hash = str(time.time()) # Fallback to ensure change detection.

        # The combination of image hash and trigger value determines the final output state.
        return f"{image_data_hash}_{force_process_trigger}"


    def _convert_tensor_nhwc_to_pil(self, tensor_nhwc, context_msg=""):
        """Safely converts a (N,H,W,C) tensor to a PIL Image."""
        if tensor_nhwc is None or tensor_nhwc.nelement() == 0: return None, "Input tensor is None or empty"
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
                 return None, f"Unsupported channel count ({channels}) for PIL conversion."
            return pil_image, None
        except Exception as e:
            print(f"[HolafEditor] Error: _convert_tensor_nhwc_to_pil failed for {context_msg}: {e}")
            return None, f"PIL creation error: {e}"

    def _convert_pil_to_tensor_nhwc(self, pil_image, target_device, original_nhwc_shape):
        """Safely converts a PIL Image back to a (N,H,W,C) tensor, matching original format."""
        if pil_image is None: return None, "PIL image is None"
        num_target_channels = original_nhwc_shape[-1]
        converted_pil_image = pil_image
        target_mode = {1: 'L', 3: 'RGB', 4: 'RGBA'}.get(num_target_channels)
        
        if target_mode and pil_image.mode != target_mode:
            try:
                converted_pil_image = pil_image.convert(target_mode)
            except Exception as e:
                 return None, f"Error converting PIL mode from {pil_image.mode} to {target_mode}: {e}"
                 
        img_np_hwc_float = np.array(converted_pil_image).astype(np.float32) / 255.0
        if converted_pil_image.mode == 'L' and img_np_hwc_float.ndim == 2:
            img_np_hwc_float = np.expand_dims(img_np_hwc_float, axis=-1)
        if img_np_hwc_float.ndim != 3 or img_np_hwc_float.shape[-1] != num_target_channels:
             return None, f"Channel mismatch after PIL conversion. Shape {img_np_hwc_float.shape} vs target channels {num_target_channels}."
        
        tensor_hwc = torch.from_numpy(img_np_hwc_float)
        tensor_nhwc = tensor_hwc.unsqueeze(0).to(target_device)
        
        if tensor_nhwc.shape[1:3] != original_nhwc_shape[1:3]:
            return None, f"Spatial dimension mismatch. Got {tensor_nhwc.shape[1:3]}, expected {original_nhwc_shape[1:3]}."
            
        return tensor_nhwc.contiguous(), None

    def save_image_and_get_info(self, tensor_nhwc, base_filename, unique_id_str=""):
        """Saves a tensor to a temp file for UI preview and returns its details."""
        pil_img, error_msg = self._convert_tensor_nhwc_to_pil(tensor_nhwc.contiguous(), f"save_image_and_get_info ({base_filename})")
        if error_msg or pil_img is None:
            print(f"[HolafEditor] Error saving temp image '{base_filename}': {error_msg}")
            return {"filename": "", "subfolder": "", "type": self.type, "error": error_msg}

        if not hasattr(self, 'save_counter'): self.save_counter = int(time.time()) % 10000
        self.save_counter += 1
        safe_base_filename = "".join(c for c in base_filename if c.isalnum() or c in ('_', '-'))
        safe_unique_id_str = "".join(c for c in unique_id_str if c.isalnum() or c in ('_', '-'))
        filename = f"holaf_editor_{safe_base_filename}_{safe_unique_id_str}_{int(time.time()*1000)}_{self.save_counter:04d}.png"
        filepath = os.path.join(self.output_dir, filename)
        
        if not os.path.exists(self.output_dir):
             try: os.makedirs(self.output_dir)
             except Exception as e: return {"filename": "", "subfolder": "", "type": self.type, "error": f"Output dir creation failed: {e}"}
        try:
            pil_img.save(filepath, compress_level=1)
            return {"filename": filename, "subfolder": "", "type": self.type}
        except Exception as e:
            print(f"[HolafEditor] Error saving file '{filepath}': {e}")
            return {"filename": "", "subfolder": "", "type": self.type, "error": f"File save error: {e}"}

    def process_images_with_apply_logic(self, image: torch.Tensor,
                                        brightness: float = 1.0, contrast: float = 1.0, saturation: float = 1.0,
                                        red_mult: float = 1.0, green_mult: float = 1.0, blue_mult: float = 1.0,
                                        unique_id=None, force_process_trigger: int = 0):
        unique_id_str = str(unique_id) if unique_id is not None else "unknownID"
        ui_info = {}
        
        # --- Input Normalization ---
        # Normalize various input formats into a single (1, H, W, C) float32 tensor.
        if image is None or not isinstance(image, torch.Tensor) or image.nelement() == 0:
            dummy = torch.zeros((1,64,64,3), dtype=torch.float32, device='cpu').contiguous()
            return {"ui": {"status":"Error: Invalid or empty input image"}, "result": (dummy.clone(), dummy.clone())}
        
        input_tensor_master = image
        input_tensor = input_tensor_master.clone()
        if input_tensor.ndim == 4 and input_tensor.shape[1] in [1, 3, 4]: # NCHW to NHWC
            input_tensor = input_tensor.permute(0, 2, 3, 1)
        
        if input_tensor.shape[0] > 1: input_tensor = input_tensor[0].unsqueeze(0) # Use first image in batch
        if not input_tensor.is_contiguous(): input_tensor = input_tensor.contiguous()
        if input_tensor.dtype != torch.float32:
             input_tensor = input_tensor.to(torch.float32) / (255.0 if input_tensor.dtype == torch.uint8 else 1.0)
        
        input_tensor_nhwc = torch.clamp(input_tensor, 0.0, 1.0)
        original_tensor_for_preview = input_tensor_nhwc.clone()

        # --- Image Processing for Live Preview ---
        # This section always runs to generate the preview image shown in the UI.
        pil_img_orig_for_preview, error_msg = self._convert_tensor_nhwc_to_pil(original_tensor_for_preview, "preview_original")
        if error_msg: return {"ui": {"status": f"Error: {error_msg}"}, "result": (original_tensor_for_preview.clone(), original_tensor_for_preview.clone())}

        pil_img_enhanced = pil_img_orig_for_preview
        try:
            if brightness != 1.0: pil_img_enhanced = ImageEnhance.Brightness(pil_img_enhanced).enhance(brightness)
            if contrast != 1.0: pil_img_enhanced = ImageEnhance.Contrast(pil_img_enhanced).enhance(contrast)
            if saturation != 1.0: pil_img_enhanced = ImageEnhance.Color(pil_img_enhanced).enhance(saturation)

            if red_mult != 1.0 or green_mult != 1.0 or blue_mult != 1.0:
                temp_img_rgb = pil_img_enhanced.convert("RGB")
                np_img_float = np.array(temp_img_rgb).astype(np.float32) / 255.0
                np_img_float[..., 0] *= red_mult
                np_img_float[..., 1] *= green_mult
                np_img_float[..., 2] *= blue_mult
                np_img_uint8 = (np.clip(np_img_float, 0.0, 1.0) * 255.0).astype(np.uint8)
                pil_img_enhanced = Image.fromarray(np_img_uint8, 'RGB')
                if pil_img_orig_for_preview.mode == 'RGBA':
                    pil_img_enhanced.putalpha(pil_img_orig_for_preview.getchannel('A'))
        except Exception as e:
            ui_info["status_enhancement_error"] = f"Enhancement error: {e}"

        modified_tensor_for_preview, error_msg = self._convert_pil_to_tensor_nhwc(pil_img_enhanced, original_tensor_for_preview.device, original_tensor_for_preview.shape)
        if error_msg: modified_tensor_for_preview = original_tensor_for_preview.clone()

        # --- Save Temp Images for UI Display ---
        original_image_details_ui = self.save_image_and_get_info(original_tensor_for_preview, "original", unique_id_str)
        modified_image_details_ui = self.save_image_and_get_info(modified_tensor_for_preview, "modified_preview", unique_id_str)
        ui_info.update({f"original_{k}": v for k,v in original_image_details_ui.items() if k!="error"})
        ui_info.update({f"modified_{k}": v for k,v in modified_image_details_ui.items() if k!="error"})

        # --- Logic for Determining Downstream Output ---
        # Create hashes to track the state of inputs and parameters.
        current_params_hash = hashlib.sha256(f"{brightness}_{contrast}_{saturation}_{red_mult}_{green_mult}_{blue_mult}".encode()).hexdigest()
        try: current_image_hash = hashlib.sha256(input_tensor_master.cpu().contiguous().numpy().tobytes()).hexdigest()
        except: current_image_hash = ""

        # The original input image is always passed through the 'original_image' output.
        output_original_image_downstream = input_tensor_master.clone()

        # Case 1: "Apply" button was clicked (`force_process_trigger` changed).
        if self.last_processed_trigger != force_process_trigger:
            # Output the currently previewed, modified image.
            output_modified_image_downstream = modified_tensor_for_preview.clone()
            # Update the state to reflect this "applied" version.
            self.last_processed_trigger = force_process_trigger
            self.last_image_hash_processed_for_downstream = current_image_hash
            self.last_params_hash_processed_for_downstream = current_params_hash
            ui_info["status"] = "Applied. Outputting current edit."
        # Case 2: No click. Decide whether to pass through the original or the last "applied" image.
        else:
            # If the input image AND parameters match the last applied state, re-output the last applied edit.
            # This handles cases where the workflow is re-queued without changes.
            if self.last_image_hash_processed_for_downstream == current_image_hash and \
               self.last_params_hash_processed_for_downstream == current_params_hash and \
               self.last_processed_trigger != -1:
                output_modified_image_downstream = modified_tensor_for_preview.clone()
                ui_info["status"] = "Re-outputting last applied edit (input/params unchanged)."
            # Otherwise (e.g., first run, or sliders changed since last apply), output the original image.
            else:
                output_modified_image_downstream = input_tensor_master.clone()
                ui_info["status"] = "Previewing. Click 'Apply' in node to output edit."

        return {"ui": ui_info, "result": (output_modified_image_downstream, output_original_image_downstream,)}