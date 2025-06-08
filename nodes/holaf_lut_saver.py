# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-23
#
# Purpose:
# This file defines the 'HolafLutSaver' custom node for ComfyUI.
# It takes a LUT data structure from a generator or loader and saves it to
# a file on the server in the standard .cube format.
#
# How it works:
# 1. Input: Receives a 'HOLAF_LUT_DATA' object, which is a dictionary
#    containing the LUT's NumPy array, its size, and a title.
# 2. Path Formatting: Allows the user to specify a base path, subfolder,
#    and filename using Python's strftime date/time formatting codes.
# 3. .cube File Writing: It constructs a valid .cube file by writing the header
#    and then iterating through the LUT data in the standard B,G,R order to
#    write each color value as a line of "R G B" floats.
# 4. Filename Uniqueness: Automatically handles filename collisions.
#
# Design Choices:
# - Standard Format: Outputs to the .cube format for maximum compatibility.
# - User-friendly Pathing: Consistent with other Holaf save nodes.
# - Standardized Data Handling: Reads the HOLAF_LUT_DATA structure assuming a
#   B,G,R indexed NumPy array.
# === End Documentation ===

import torch
import numpy as np
import os
import datetime
import folder_paths

class HolafLutSaver:
    def __init__(self):
        # Default the save directory to the 'luts' model folder
        self.output_dir = folder_paths.get_folder_paths("luts")[0]

    @classmethod
    def INPUT_TYPES(s):
        default_luts_path = folder_paths.get_folder_paths("luts")[0]
        
        return {
            "required": {
                "holaf_lut_data": ("HOLAF_LUT_DATA",),
                "base_path": ("STRING", {"default": default_luts_path}),
                "subfolder": ("STRING", {"default": ""}),
                "filename": ("STRING", {"default": "%Y-%m-%d-%Hh%Mm%Ss_lut"}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_lut"
    OUTPUT_NODE = True
    CATEGORY = "Holaf/LUT"

    def get_unique_filepath(self, directory, base_filename, ext):
        filepath = os.path.join(directory, f"{base_filename}{ext}")
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(directory, f"{base_filename}_{counter:04d}{ext}")
            counter += 1
        return filepath, os.path.basename(filepath)

    def save_lut(self, holaf_lut_data: dict, base_path: str, subfolder: str, filename: str):
        if not isinstance(holaf_lut_data, dict) or not all(k in holaf_lut_data for k in ['lut', 'size']):
            print("[HolafLutSaver] Error: Invalid HOLAF_LUT_DATA input. Expected a dict with 'lut' and 'size' keys.")
            return {}

        lut_np = holaf_lut_data.get('lut')
        size = holaf_lut_data.get('size')
        title = holaf_lut_data.get('title', 'Untitled Holaf LUT')

        if not isinstance(lut_np, np.ndarray) or not isinstance(size, int):
            print("[HolafLutSaver] Error: Malformed HOLAF_LUT_DATA content.")
            return {}
            
        now = datetime.datetime.now()

        try:
            formatted_subfolder = now.strftime(subfolder)
        except Exception as e:
            print(f"[HolafLutSaver] Warning: Error formatting subfolder string '{subfolder}'. Using it as is. Error: {e}")
            formatted_subfolder = subfolder

        try:
            formatted_filename_base = now.strftime(filename)
        except Exception as e:
            print(f"[HolafLutSaver] Warning: Error formatting filename string '{filename}'. Using it as is. Error: {e}")
            formatted_filename_base = filename

        output_path = os.path.join(base_path, formatted_subfolder)
        os.makedirs(output_path, exist_ok=True)

        final_filepath, final_filename = self.get_unique_filepath(output_path, formatted_filename_base, ".cube")

        try:
            with open(final_filepath, 'w', encoding='utf-8') as f:
                f.write(f'TITLE "{title}"\n')
                f.write(f'LUT_3D_SIZE {size}\n\n')
                
                # <--- MODIFICATION : ASSURER LE BON ORDRE D'ÉCRITURE --->
                # The standard .cube format iterates through R, then G, then B.
                # Our NumPy array is indexed as [B, G, R]. So, the loop order must be b, g, r.
                for b in range(size):
                    for g in range(size):
                        for r in range(size):
                            # Get the RGB triplet from our NumPy array at the correct index
                            # Note: The output format is R G B, but our array access is B, G, R
                            rgb_values = lut_np[b, g, r]
                            line = f"{rgb_values[0]:.6f} {rgb_values[1]:.6f} {rgb_values[2]:.6f}\n"
                            f.write(line)
                # <--- FIN MODIFICATION --->
            
            print(f"[HolafLutSaver] Successfully saved LUT to: {final_filepath}")

        except Exception as e:
            print(f"[HolafLutSaver] Error writing .cube file to {final_filepath}: {e}")
            return {"ui": {"saved_luts": [{"filename": final_filename, "error": str(e)}]}}

        return {"ui": {"saved_luts": [{"filename": final_filename}]}}