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

import os
import json
import datetime
import numpy as np
from PIL import Image
import folder_paths

class HolafSaveImage:
    """
    Saves images with advanced control over the output path and filename.
    It can also save the prompt and the full workflow graph as separate
    .txt and .json files alongside the image.
    """
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                # The root directory for saving files.
                "base_path": ("STRING", {"default": folder_paths.get_output_directory()}),
                # Subfolder within the base path; supports strftime date/time formatting (e.g., `%Y-%m-%d`).
                "subfolder": ("STRING", {"default": "%Y-%m-%d"}),
                # Filename pattern (without extension); also supports strftime formatting.
                "filename": ("STRING", {"default": "%Y-%m-%d-%Hh%Mm%Ss"}),
                "save_prompt": ("BOOLEAN", {"default": True}),
                "save_workflow": ("BOOLEAN", {"default": True}),
            },
            # Hidden inputs are the standard ComfyUI way to access the full prompt and workflow data.
            "hidden": {"prompt_hidden": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING",)
    RETURN_NAMES = ("image", "prompt", "workflow_json", "help_string",)
    FUNCTION = "save_image"
    OUTPUT_NODE = True
    CATEGORY = "Holaf"

    def get_unique_filepath(self, directory, base_filename, ext):
        """
        Prevents overwriting files by appending a numeric suffix if the
        target filename already exists (e.g., `image_0001.png`).
        """
        filepath = os.path.join(directory, f"{base_filename}{ext}")
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(directory, f"{base_filename}_{counter:04d}{ext}")
            counter += 1
        return filepath, os.path.basename(filepath)

    def save_image(self, image, prompt, base_path, subfolder, filename, save_prompt, save_workflow, prompt_hidden=None, extra_pnginfo=None):
        """
        Saves the image and optional metadata based on the provided settings.
        """
        # This string provides in-UI help for the user.
        help_string = """...""" # Content omitted for brevity
        
        now = datetime.datetime.now()

        # Format subfolder and filename using strftime codes for dynamic path creation.
        try:
            formatted_subfolder = now.strftime(subfolder)
        except Exception as e:
            # Fallback to a simple date format if the user's string is invalid.
            formatted_subfolder = now.strftime('%Y-%m-%d')

        try:
            formatted_filename_base = now.strftime(filename)
        except Exception as e:
            # Fallback to a simple datetime format if the user's string is invalid.
            formatted_filename_base = now.strftime('%Y-%m-%d-%Hh%Mm%Ss')

        # Construct the full output path and create the directory if it doesn't exist.
        output_path = os.path.join(base_path, formatted_subfolder)
        os.makedirs(output_path, exist_ok=True)
        
        # --- File Saving Logic ---
        img_array = (image.cpu().numpy() * 255.0).astype(np.uint8)
        
        results = []
        workflow_json = ""
        
        # Process and save each image in the batch individually.
        for i in range(img_array.shape[0]):
            # For each image, generate a unique filename to prevent conflicts.
            image_path, final_image_filename = self.get_unique_filepath(output_path, formatted_filename_base, ".png")
            final_filename_base = os.path.splitext(final_image_filename)[0]

            img = Image.fromarray(img_array[i])
            try:
                img.save(image_path, pnginfo=None, compress_level=4)
                # Append info for the UI to display the saved image.
                results.append({
                    "filename": final_image_filename,
                    "subfolder": formatted_subfolder,
                    "type": self.type
                })
            except Exception as e:
                 print(f"[Holaf Save Image] Error saving image {image_path}: {e}")

            # If enabled, save the prompt to a corresponding .txt file.
            if save_prompt and prompt:
                prompt_path = os.path.join(output_path, f"{final_filename_base}.txt")
                try:
                    with open(prompt_path, 'w', encoding='utf-8') as f:
                        f.write(prompt)
                except Exception as e:
                    print(f"[Holaf Save Image] Error saving prompt {prompt_path}: {e}")

            # The workflow is identical for all images in a batch, so we only need to
            # process and serialize it once as an optimization.
            if i == 0:
                workflow_data_to_save = extra_pnginfo.get('workflow') if extra_pnginfo else prompt_hidden
                if workflow_data_to_save:
                    try:
                        workflow_json = json.dumps(workflow_data_to_save, indent=2)
                    except Exception as e:
                        workflow_json = json.dumps({"error": f"Failed to serialize workflow: {e}"})

            # If enabled, save the processed workflow to a corresponding .json file.
            if save_workflow and workflow_json:
                workflow_path = os.path.join(output_path, f"{final_filename_base}.json")
                try:
                    with open(workflow_path, 'w', encoding='utf-8') as f:
                        f.write(workflow_json)
                except Exception as e:
                    print(f"[Holaf Save Image] Error saving workflow {workflow_path}: {e}")

        # Return UI feedback and pass through the original data for chaining.
        return {"ui": {"images": results}, "result": (image, prompt, workflow_json, help_string,)}