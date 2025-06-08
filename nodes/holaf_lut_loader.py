# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-23
#
# Purpose:
# This file defines the 'HolafLutLoader' node. It provides a simple dropdown menu
# to select a .cube LUT file from the 'ComfyUI/models/luts' directory and
# load it for use in a workflow.
#
# How it works:
# 1. Folder Registration: Ensures the 'luts' subfolder inside 'models' is
#    recognized by ComfyUI.
# 2. File Discovery: Uses ComfyUI's 'folder_paths.get_filename_list("luts")'
#    to dynamically populate a dropdown menu with all available .cube files.
# 3. Node Execution: When the node runs, it takes the selected filename from the
#    dropdown, finds its full path, parses the .cube file, and outputs the
#    data in the standard 'HOLAF_LUT_DATA' format.
# === End Documentation ===

import numpy as np
import os
import re
import folder_paths

# --- Folder Path Registration ---
# This ensures ComfyUI knows about the 'luts' folder inside 'models'
luts_dir = os.path.join(folder_paths.models_dir, "luts")
if not os.path.exists(luts_dir):
    os.makedirs(luts_dir)
# This makes "luts" a valid category for folder_paths functions
folder_paths.add_model_folder_path("luts", luts_dir)


class HolafLutLoader:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        # Get a list of all files in the 'luts' directory
        # This list will populate the dropdown menu in the UI.
        lut_files = folder_paths.get_filename_list("luts")
        
        # Add a "None" option in case no file is desired.
        if not lut_files:
            print("Warning: No LUT files found in the 'models/luts' directory.")
            lut_files = ["None"]
        
        return {
            "required": {
                "lut_name": (lut_files, ),
            },
        }

    RETURN_TYPES = ("HOLAF_LUT_DATA",)
    RETURN_NAMES = ("holaf_lut_data",)
    FUNCTION = "load_lut"
    CATEGORY = "Holaf/LUT"
    
    def load_lut(self, lut_name: str):
        # If the user selects "None" or if the list was empty.
        if not lut_name or lut_name == "None":
            # Return an empty but valid data structure to avoid errors downstream
            print("[HolafLutLoader] No LUT selected. Passing empty data.")
            return ({"lut": np.array([]), "size": 0, "title": "None"},)

        # Get the full, absolute path to the selected LUT file
        lut_path = folder_paths.get_full_path("luts", lut_name)

        if not lut_path or not os.path.exists(lut_path):
            raise FileNotFoundError(f"LUT file '{lut_name}' not found in the 'luts' directory.")
        
        print(f"[HolafLutLoader] Loading LUT from: {lut_path}")
        
        title, size, lut_data_flat = "", 0, []
        
        try:
            with open(lut_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'): continue
                    
                    if line.startswith('TITLE'):
                        title = (re.findall(r'"([^"]*)"', line) or [""])[0]
                    elif line.startswith('LUT_3D_SIZE'):
                        size = int(line.split()[-1])
                    elif size > 0:
                        values = [float(v) for v in line.split()]
                        if len(values) == 3: lut_data_flat.append(values)
        except Exception as e:
            raise IOError(f"Error reading or parsing LUT file '{lut_name}': {e}")
        
        if size == 0 or len(lut_data_flat) != size ** 3:
            raise ValueError(f"Failed to parse LUT '{lut_name}'. Check file format, size, and content.")
            
        # Reshape the flat list of values into the 3D LUT cube
        lut_np = np.array(lut_data_flat, dtype=np.float32).reshape(size, size, size, 3)

        # Prepare the output data structure
        holaf_lut_data = {
            "lut": lut_np,
            "size": size,
            "title": title if title else os.path.splitext(lut_name)[0]
        }
        
        return (holaf_lut_data,)