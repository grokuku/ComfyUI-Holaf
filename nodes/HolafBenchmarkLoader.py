import torch
import folder_paths
import comfy.sd
import os

# ==================================================================================
# HolafBenchmarkLoader Node - Documentation
# ==================================================================================
#
# Author: Cline (AI Assistant) for Holaf
# Date: 2025-04-02 (Updated)
#
# Purpose:
# This node loads specified SD checkpoint models and/or FLUX UNet models.
# It outputs a list containing information about each loaded model (object, name, type)
# for use with HolafBenchmarkRunner.
#
# How it works:
# 1. Provides dropdown lists for SD checkpoints (`ckpt_name`, `ckpt_name_2`) and
#    FLUX UNet files (`flux_unet_name_1`, `flux_unet_name_2`).
# 2. When executed, it loads the selected models/UNets using appropriate ComfyUI functions
#    (`comfy.sd.load_checkpoint_guess_config` for SD, `comfy.sd.load_unet` for FLUX).
# 3. Outputs a list of dictionaries, where each dictionary contains:
#    - 'model': The loaded model object (SD model or FLUX UNet).
#    - 'name': The filename of the loaded model/UNet.
#    - 'type': A string indicating the model type ('SD' or 'FLUX').
#
# Inputs:
# - ckpt_name (COMBO): Optional: The filename of the first SD checkpoint model.
# - ckpt_name_2 (COMBO): Optional: The filename of the second SD checkpoint model.
# - flux_unet_name_1 (COMBO): Optional: The filename of the first FLUX UNet model.
# - flux_unet_name_2 (COMBO): Optional: The filename of the second FLUX UNet model.
#   (At least one model must be selected).
#
# Outputs:
# - holaf_model_info_list (HOLAF_MODEL_INFO_LIST): A list containing dictionaries,
#   each describing a loaded model/UNet.
#
# Dependencies:
# - Relies on ComfyUI's internal modules: torch, folder_paths, comfy.sd.
#
# Error Handling:
# - Includes basic error handling for model loading failures.
# - Raises an error if no models are selected.
#
# ==================================================================================

class HolafBenchmarkLoader:
    @classmethod
    def INPUT_TYPES(s):
        # Add "None" to allow deselecting
        checkpoint_list = ["None"] + folder_paths.get_filename_list("checkpoints")
        unet_list = ["None"] + folder_paths.get_filename_list("unet") # Get UNet files

        return {
            "required": {}, # Nothing strictly required, user must select at least one
            "optional": {
                 "ckpt_name": (checkpoint_list, {"default": "None"}),
                 "ckpt_name_2": (checkpoint_list, {"default": "None"}),
                 "flux_unet_name_1": (unet_list, {"default": "None"}), # Input for FLUX UNet 1
                 "flux_unet_name_2": (unet_list, {"default": "None"}), # Input for FLUX UNet 2
                 }
            }

    RETURN_TYPES = ("HOLAF_MODEL_INFO_LIST",) # Keep custom list output type
    RETURN_NAMES = ("holaf_model_info_list",) # Keep name for the list output
    FUNCTION = "load_benchmark_models"
    CATEGORY = "Holaf"

    def _load_single_model(self, ckpt_name):
        """Helper function to load a single checkpoint."""
        if not ckpt_name or ckpt_name == "None":
            return None, None # Return None if no name provided

        print(f"[HolafBenchmarkLoader] Loading checkpoint: {ckpt_name}")
        ckpt_path = folder_paths.get_full_path("checkpoints", ckpt_name)
        if not ckpt_path:
            raise FileNotFoundError(f"Checkpoint file not found in checkpoints folder: {ckpt_name}")

        # Load the checkpoint using ComfyUI's function
        loaded_model, clip, vae, clip_vision_output = comfy.sd.load_checkpoint_guess_config(
            ckpt_path,
            output_vae=True,
            output_clip=True,
            embedding_directory=folder_paths.get_folder_paths("embeddings")
        )

        if loaded_model is None:
             raise ValueError(f"Model loading failed for '{ckpt_name}', returned None.")

        print(f"[HolafBenchmarkLoader] Checkpoint '{ckpt_name}' loaded successfully.")
        return loaded_model, ckpt_name

    def _load_single_unet(self, unet_name):
        """Helper function to load a single UNet."""
        if not unet_name or unet_name == "None":
            return None, None # Return None if no name provided

        print(f"[HolafBenchmarkLoader] Loading UNet: {unet_name}")
        unet_path = folder_paths.get_full_path("unet", unet_name)
        if not unet_path:
            raise FileNotFoundError(f"UNet file not found in unet folder: {unet_name}")

        # Load the UNet using ComfyUI's function
        loaded_unet = comfy.sd.load_unet(unet_path)

        if loaded_unet is None:
             raise ValueError(f"UNet loading failed for '{unet_name}', returned None.")

        print(f"[HolafBenchmarkLoader] UNet '{unet_name}' loaded successfully.")
        # Return the UNet object itself (which is the 'model' for sampling in this context)
        return loaded_unet, unet_name

    # Updated function signature to accept UNet names
    def load_benchmark_models(self, ckpt_name="None", ckpt_name_2="None", flux_unet_name_1="None", flux_unet_name_2="None"):
        """Loads selected SD models and/or FLUX UNets and returns them as a list of dictionaries."""
        model_info_list = []
        loaded_names = set() # Keep track of loaded names to avoid duplicates

        # --- Process SD Checkpoints ---
        for name in [ckpt_name, ckpt_name_2]:
            if name and name != "None" and name not in loaded_names:
                try:
                    model, loaded_name = self._load_single_model(name)
                    if model:
                        model_info_list.append({'model': model, 'name': loaded_name, 'type': 'SD'})
                        loaded_names.add(loaded_name)
                except Exception as e_sd:
                     print(f"[HolafBenchmarkLoader] Warning: Failed to load SD model '{name}': {e_sd}. Skipping.")
            elif name in loaded_names:
                 print(f"[HolafBenchmarkLoader] Info: SD model name '{name}' already loaded or selected multiple times. Skipping duplicate.")

        # --- Process FLUX UNets ---
        for name in [flux_unet_name_1, flux_unet_name_2]:
             if name and name != "None" and name not in loaded_names:
                 try:
                     unet_model, loaded_name = self._load_single_unet(name)
                     if unet_model:
                         # Store the UNet object directly under the 'model' key
                         model_info_list.append({'model': unet_model, 'name': loaded_name, 'type': 'FLUX'})
                         loaded_names.add(loaded_name)
                 except Exception as e_unet:
                      print(f"[HolafBenchmarkLoader] Warning: Failed to load FLUX UNet '{name}': {e_unet}. Skipping.")
             elif name in loaded_names:
                  print(f"[HolafBenchmarkLoader] Info: FLUX UNet name '{name}' already loaded or selected multiple times. Skipping duplicate.")

        # --- Validation ---
        if not model_info_list:
             raise ValueError("No models or UNets were selected or loaded successfully. Please select at least one valid model.")

        # Return the list containing dictionaries
        print(f"[HolafBenchmarkLoader] Successfully loaded {len(model_info_list)} model(s)/UNet(s): {[item['name'] for item in model_info_list]}")
        return (model_info_list,)

# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "HolafBenchmarkLoader": HolafBenchmarkLoader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafBenchmarkLoader": "Benchmark Loader (Holaf)"
}
