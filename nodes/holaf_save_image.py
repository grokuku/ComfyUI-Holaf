# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-01
#
# Purpose:
# This file defines the 'HolafSaveImage' custom node for ComfyUI.
# Its primary function is to save generated images to disk, along with optional
# associated metadata: the text prompt in a `.txt` file and the workflow
# structure in a `.json` file. It provides enhanced control over the output
# directory structure and filenames compared to the standard save node.
#
# Design Choices & Rationale:
# - Flexible Path/Filename Formatting: Uses Python's `strftime` formatting codes
#   for both the `subfolder` and `filename` inputs. This allows users to
#   automatically organize outputs by date, time, or other temporal components
#   (e.g., creating daily folders like "2025-04-01").
# - Separate Metadata Files: Instead of embedding prompt/workflow data into the
#   PNG metadata (which can have limitations or be stripped), this node saves
#   them as separate `.txt` (prompt) and `.json` (workflow) files alongside the
#   image. This keeps the image file clean and makes metadata easily accessible
#   for external tools or scripts.
# - Filename Collision Handling: Implements a `get_unique_filepath` helper function
#   to automatically append a numeric suffix (e.g., "_0001", "_0002") if a file
#   with the target name already exists. This prevents accidental overwriting of files.
#   The unique base name is then consistently used for the image, prompt, and workflow files.
# - Directory Management: Creates the specified output directory (`base_path`/`subfolder`)
#   if it doesn't exist, including error handling and a fallback to the default
#   ComfyUI output directory if creation fails.
# - User Control: Provides boolean toggles (`save_prompt`, `save_workflow`) to
#   allow users to decide whether to save the associated metadata files.
# - Batch Handling: Correctly processes batches of images, saving each image
#   individually and ensuring unique filenames (and corresponding metadata filenames)
#   are generated for each image within the batch if necessary.
# - Passthrough & Help Outputs: Passes the input image and prompt through as outputs
#   for potential chaining. Also outputs the workflow JSON as a string and provides
#   a detailed `help_string` output for in-UI guidance.
# === End Documentation ===

import os
import json
import datetime
import torch
import numpy as np
from PIL import Image
import folder_paths
import comfy.sd

class HolafSaveImage:
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"

    @classmethod
    def INPUT_TYPES(s):
        # Default format string for subfolder
        default_subfolder_format = "%Y-%m-%d"
        return {
            "required": {
                "image": ("IMAGE",),
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                "base_path": ("STRING", {"default": folder_paths.get_output_directory()}),
                "subfolder": ("STRING", {"default": default_subfolder_format}), # Use format string as default for UI
                "filename": ("STRING", {"default": "%Y-%m-%d-%Hh%Mm%Ss"}), # New default filename format
                "save_prompt": ("BOOLEAN", {"default": True}),
                "save_workflow": ("BOOLEAN", {"default": True}), # Changed default to True
            },
            "hidden": {"prompt_hidden": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING",)
    RETURN_NAMES = ("image", "prompt", "workflow_json", "help_string",)
    FUNCTION = "save_image"
    OUTPUT_NODE = True
    CATEGORY = "Holaf"

    def get_unique_filepath(self, directory, base_filename, ext):
        """Checks for existing files and returns a unique path with a numeric suffix if needed."""
        filepath = os.path.join(directory, f"{base_filename}{ext}")
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(directory, f"{base_filename}_{counter:04d}{ext}")
            counter += 1
        return filepath, os.path.basename(filepath) # Return full path and just the final filename

    def save_image(self, image, prompt, base_path, subfolder, filename, save_prompt, save_workflow, prompt_hidden=None, extra_pnginfo=None):

        help_string = """
        **Holaf Save Image Node Help**

        This node saves images, prompts, and workflow data.

        **Parameters:**
        - `base_path`: The root directory where files will be saved. Defaults to the ComfyUI output directory.
        - `subfolder`: The subfolder within the base path. Supports date/time formatting using standard Python strftime codes. Default: `%Y-%m-%d`.
        - `filename`: The pattern for the output filename (without extension). Supports date/time formatting using standard Python strftime codes. Default: `%H-%M-%S`.
            **Available Format Codes:**
            - `%Y`: Year (e.g., 2025)
            - `%m`: Month (01-12)
            - `%d`: Day (01-31)
            - `%H`: Hour (24-hour clock, 00-23)
            - `%M`: Minute (00-59)
            - `%S`: Second (00-59)
            *(Literal characters like 'h', 'm', 's' can be included directly)*
            Example: `base_path="outputs", subfolder="%Y-%m-%d", filename="%Y-%m-%d-%Hh%Mm%Ss"` -> `outputs/2025-03-30/2025-03-30-15h41m10s.png`
        - `save_prompt`: If checked, saves the prompt text to a `.txt` file alongside the image.
        - `save_workflow`: If checked, saves the workflow data to a `.json` file alongside the image. (Note: Workflow data is retrieved from hidden inputs).
        - **Filename Conflicts:** If a file with the generated name already exists, a suffix like `_0001`, `_0002` will be added.

        **Outputs:**
        - `image`: The input image (passed through).
        - `prompt`: The input prompt text (passed through).
        - `workflow_json`: The workflow data as a JSON string.
        - `help_string`: This help text.
        """

        now = datetime.datetime.now()

        # Format subfolder and filename with date/time
        try:
            formatted_subfolder = now.strftime(subfolder)
        except Exception as e:
            print(f"[Holaf Save Image] Error formatting subfolder string '{subfolder}': {e}. Using default date.")
            formatted_subfolder = now.strftime('%Y-%m-%d') # Fallback

        try:
            formatted_filename_base = now.strftime(filename)
        except Exception as e:
            print(f"[Holaf Save Image] Error formatting filename string '{filename}': {e}. Using new default format.")
            formatted_filename_base = now.strftime('%Y-%m-%d-%Hh%Mm%Ss') # Updated Fallback

        # Construct the full output directory path
        output_path = os.path.join(base_path, formatted_subfolder)

        # Create output directory (base + subfolder) if it doesn't exist
        if not os.path.exists(output_path):
            try:
                os.makedirs(output_path, exist_ok=True)
                print(f"[Holaf Save Image] Created directory: {output_path}")
            except OSError as e:
                print(f"[Holaf Save Image] Error creating directory {output_path}: {e}")
                # Fallback to default output directory if creation fails
                output_path = self.output_dir
                if not os.path.exists(output_path):
                     os.makedirs(output_path, exist_ok=True)
                formatted_subfolder = "" # Reset subfolder if using fallback


        # --- Filename Conflict Resolution & Path Generation ---
        image_path, final_image_filename = self.get_unique_filepath(output_path, formatted_filename_base, ".png")
        # Use the base name derived from the unique image path for other files
        final_filename_base = os.path.splitext(final_image_filename)[0]
        prompt_path = os.path.join(output_path, f"{final_filename_base}.txt")
        workflow_path = os.path.join(output_path, f"{final_filename_base}.json")


        # --- Image Saving ---
        # Convert tensor to PIL image
        img_array = image.cpu().numpy() * 255.0
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        
        results = list()
        for i in range(img_array.shape[0]):
            img = Image.fromarray(img_array[i])
            # Save image WITHOUT workflow metadata
            try:
                # Use the unique image_path determined earlier
                img.save(image_path, pnginfo=None, compress_level=4)
                print(f"[Holaf Save Image] Saved image to {image_path}")
                results.append({
                    "filename": final_image_filename, # Use the potentially suffixed filename
                    "subfolder": formatted_subfolder, # Use the formatted subfolder name
                    "type": self.type
                })
                # If saving multiple images in a batch, we need unique names for subsequent ones
                if img_array.shape[0] > 1 and i < img_array.shape[0] - 1:
                     image_path, final_image_filename = self.get_unique_filepath(output_path, formatted_filename_base, ".png")
                     final_filename_base = os.path.splitext(final_image_filename)[0]
                     prompt_path = os.path.join(output_path, f"{final_filename_base}.txt")
                     workflow_path = os.path.join(output_path, f"{final_filename_base}.json")

            except Exception as e:
                 print(f"[Holaf Save Image] Error saving image {image_path}: {e}")


        # --- Prompt Saving ---
        # Use the potentially updated prompt_path from the loop (for batches)
        if save_prompt and prompt:
            try:
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(prompt)
                print(f"[Holaf Save Image] Saved prompt to {prompt_path}")
            except Exception as e:
                print(f"[Holaf Save Image] Error saving prompt {prompt_path}: {e}")

        # --- Workflow Saving ---
        # Use the potentially updated workflow_path from the loop (for batches)
        workflow_json = ""
        if prompt_hidden is not None:
            try:
                # Serialize the original workflow data directly for the output string
                workflow_json = json.dumps(prompt_hidden, indent=2)
                
                # Save the workflow file if requested
                if save_workflow:
                    with open(workflow_path, 'w', encoding='utf-8') as f:
                        f.write(workflow_json) # Write the standard JSON
                    print(f"[Holaf Save Image] Saved workflow to {workflow_path}")

            except Exception as e:
                 print(f"[Holaf Save Image] Error serializing/saving workflow: {e}")
                 workflow_json = json.dumps({"error": f"Failed to serialize/save workflow: {e}"})


        return {"ui": {"images": results}, "result": (image, prompt, workflow_json, help_string,)}


# Node registration
NODE_CLASS_MAPPINGS = {
    "HolafSaveImage": HolafSaveImage
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafSaveImage": "Save Image (Holaf)"
}
