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
import folder_paths
import comfy.sd
import os

class HolafBenchmarkLoader:
    """
    Loads selected Stable Diffusion checkpoints and/or FLUX UNets.
    It packages the loaded model objects with their names and types into a
    list, which serves as the input for the HolafBenchmarkRunner node.
    """
    @classmethod
    def INPUT_TYPES(s):
        # Dynamically populate dropdowns and add a "None" option to allow deselecting a model.
        try:
            checkpoint_list = ["None"] + folder_paths.get_filename_list("checkpoints")
        except:
            checkpoint_list = ["None"]
            print("[HolafBenchmarkLoader] Warning: Could not access checkpoints folder.")

        try:
            unet_list = ["None"] + folder_paths.get_filename_list("unet")
        except:
            unet_list = ["None"]
            print("[HolafBenchmarkLoader] Warning: Could not access unet folder.")

        return {
            "required": {}, # Nothing is strictly required.
            "optional": { # User can select models from any of these optional slots.
                 "ckpt_name": (checkpoint_list, {"default": "None"}),
                 "ckpt_name_2": (checkpoint_list, {"default": "None"}),
                 "flux_unet_name_1": (unet_list, {"default": "None"}),
                 "flux_unet_name_2": (unet_list, {"default": "None"}),
                 }
            }

    RETURN_TYPES = ("HOLAF_MODEL_INFO_LIST",)
    RETURN_NAMES = ("holaf_model_info_list",)
    FUNCTION = "load_benchmark_models"
    CATEGORY = "Holaf"

    def _load_single_model(self, ckpt_name):
        """Helper function to load a single SD checkpoint."""
        if not ckpt_name or ckpt_name == "None":
            return None, None
        ckpt_path = folder_paths.get_full_path("checkpoints", ckpt_name)
        loaded_model, _, _, _ = comfy.sd.load_checkpoint_guess_config(
            ckpt_path, output_vae=True, output_clip=True,
            embedding_directory=folder_paths.get_folder_paths("embeddings"))
        return loaded_model, ckpt_name

    def _load_single_unet(self, unet_name):
        """Helper function to load a single FLUX UNet."""
        if not unet_name or unet_name == "None":
            return None, None
        unet_path = folder_paths.get_full_path("unet", unet_name)
        loaded_unet = comfy.sd.load_unet(unet_path)
        return loaded_unet, unet_name

    def load_benchmark_models(self, ckpt_name="None", ckpt_name_2="None", flux_unet_name_1="None", flux_unet_name_2="None"):
        """
        Loads the selected models and returns them as a list of dictionaries.
        Each dictionary contains the model object, its name, and its type ('SD' or 'FLUX').
        """
        model_info_list = []
        loaded_names = set() # Use a set to prevent loading the same model twice.

        # Process all selected models and UNets.
        selections = [
            (ckpt_name, self._load_single_model, 'SD'),
            (ckpt_name_2, self._load_single_model, 'SD'),
            (flux_unet_name_1, self._load_single_unet, 'FLUX'),
            (flux_unet_name_2, self._load_single_unet, 'FLUX')
        ]

        for name, load_func, model_type in selections:
            if name and name != "None" and name not in loaded_names:
                try:
                    model, loaded_name = load_func(name)
                    if model:
                        # Package the data into the specific format for the Runner.
                        model_info_list.append({'model': model, 'name': loaded_name, 'type': model_type})
                        loaded_names.add(loaded_name)
                        print(f"[HolafBenchmarkLoader] Successfully loaded '{loaded_name}'.")
                except Exception as e:
                     print(f"[HolafBenchmarkLoader] Warning: Failed to load '{name}': {e}. Skipping.")
        
        if not model_info_list:
             raise ValueError("No models or UNets were selected or loaded successfully.")

        return (model_info_list,)