import torch
import folder_paths
import comfy.sd
import os

# ==================================================================================
# HolafBenchmarkLoader Node - Documentation
# ==================================================================================
#
# Author: Cline (AI Assistant) for Holaf
# Date: 2025-04-01
#
# Purpose:
# This node loads a specified checkpoint model and outputs both the loaded model object
# and the filename of the checkpoint. It's designed to be used in conjunction with
# HolafBenchmarkRunner to provide it with the necessary model and its name.
#
# How it works:
# 1. Provides a dropdown list (`ckpt_name`) of available checkpoint files.
# 2. When executed, it loads the selected checkpoint using ComfyUI's standard
#    loading functions (`comfy.sd.load_checkpoint_guess_config`).
# 3. Outputs the loaded model object (`MODEL`) and the selected checkpoint
#    filename (`STRING`).
#
# Inputs:
# - ckpt_name (COMBO): The filename of the first checkpoint model to load.
# - ckpt_name_2 (COMBO): Optional: The filename of the second checkpoint model to load for comparison.
#
# Outputs:
# - holaf_model_info_list (HOLAF_MODEL_INFO_LIST): A list containing one or two tuples.
#   Each tuple is (model_object, ckpt_name_string).
#
# Dependencies:
# - Relies on ComfyUI's internal modules: torch, folder_paths, comfy.sd.
#
# Error Handling:
# - Includes basic error handling for model loading failures.
#
# ==================================================================================

class HolafBenchmarkLoader:
    @classmethod
    def INPUT_TYPES(s):
        checkpoint_list = folder_paths.get_filename_list("checkpoints")
        # Add a "None" option to the second list to make it optional
        checkpoint_list_optional = ["None"] + checkpoint_list
        return {
            "required": {
                 "ckpt_name": (checkpoint_list, ),
                 },
            "optional": {
                 "ckpt_name_2": (checkpoint_list_optional, {"default": "None"}),
                 }
            }

    RETURN_TYPES = ("HOLAF_MODEL_INFO_LIST",) # Define custom list output type
    RETURN_NAMES = ("holaf_model_info_list",) # Name for the list output
    FUNCTION = "load_benchmark_models" # Renamed function
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

    def load_benchmark_models(self, ckpt_name, ckpt_name_2="None"):
        """Loads one or two models and returns them as a list of tuples."""
        model_info_list = []

        try:
            # Load the first model (required)
            model1, name1 = self._load_single_model(ckpt_name)
            if model1:
                model_info_list.append((model1, name1))
            else:
                # If the first model fails to load, we can't proceed
                raise ValueError(f"Failed to load the primary model: {ckpt_name}")

            # Load the second model (optional)
            if ckpt_name_2 and ckpt_name_2 != "None" and ckpt_name_2 != ckpt_name:
                try:
                    model2, name2 = self._load_single_model(ckpt_name_2)
                    if model2:
                        model_info_list.append((model2, name2))
                    # If model2 loading fails, we just proceed with model1
                except Exception as e_model2:
                     print(f"[HolafBenchmarkLoader] Warning: Failed to load second model '{ckpt_name_2}': {e_model2}. Proceeding with only the first model.")
            elif ckpt_name_2 == ckpt_name:
                 print(f"[HolafBenchmarkLoader] Info: Second model name is the same as the first. Only loading one model.")


            # Return the list containing one or two tuples
            return (model_info_list,)

        except Exception as e:
            print(f"[HolafBenchmarkLoader] Error during model loading process: {e}")
            # import traceback # Uncomment for detailed debug info
            # print(traceback.format_exc())
            # How to handle errors? Return None? Raise exception?
            # Returning None might break downstream nodes expecting a model.
            # Raising might stop the workflow. Let's re-raise for now.
            raise e # Re-raise the exception to halt execution clearly

# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "HolafBenchmarkLoader": HolafBenchmarkLoader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafBenchmarkLoader": "Benchmark Loader (Holaf)"
}
