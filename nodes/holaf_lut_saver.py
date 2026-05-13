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

import numpy as np
import os
import datetime
import folder_paths

def _validate_lut_path(base_path, allowed_base=None):
    """Prevent path traversal by ensuring resolved path stays within allowed_base."""
    if allowed_base is None:
        allowed_base = folder_paths.get_output_directory()
    abs_base = os.path.abspath(os.path.expanduser(base_path))
    abs_allowed = os.path.abspath(allowed_base)
    if not (abs_base == abs_allowed or abs_base.startswith(abs_allowed + os.sep)):
        return allowed_base
    return base_path

class HolafLutSaver:
    """
    Saves a HOLAF_LUT_DATA object, typically from a generator or loader node,
    to a standard .cube file. It provides flexible naming and path options,
    including date/time formatting.
    """
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()

    @classmethod
    def INPUT_TYPES(s):
        default_luts_path = folder_paths.get_output_directory()
        
        return {
            "required": {
                # The custom data structure containing the LUT to be saved.
                "holaf_lut_data": ("HOLAF_LUT_DATA",),
                # The root directory where the LUT will be saved.
                "base_path": ("STRING", {"default": default_luts_path}),
                # An optional subfolder; supports strftime date/time formatting.
                "subfolder": ("STRING", {"default": ""}),
                # The filename for the LUT; also supports strftime formatting.
                "filename": ("STRING", {"default": "%Y-%m-%d-%Hh%Mm%Ss_lut"}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_lut"
    OUTPUT_NODE = True
    CATEGORY = "Holaf/LUT"

    def get_unique_filepath(self, directory, base_filename, ext):
        """
        Ensures that files are not accidentally overwritten. If a file with the
        target name already exists, it appends a numeric suffix (e.g., 'filename_0001.cube').
        """
        filepath = os.path.join(directory, f"{base_filename}{ext}")
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(directory, f"{base_filename}_{counter:04d}{ext}")
            counter += 1
        return filepath, os.path.basename(filepath)

    def save_lut(self, holaf_lut_data: dict, base_path: str, subfolder: str, filename: str):
        """
        Handles the entire save process: path creation, filename formatting,
        and writing the .cube file content.
        """
        # First, validate the incoming LUT data to ensure it has the required structure and content.
        if not isinstance(holaf_lut_data, dict) or not all(k in holaf_lut_data for k in ['lut', 'size']):
            print("[HolafLutSaver] Error: Invalid HOLAF_LUT_DATA input.")
            return {}

        lut_np = holaf_lut_data.get('lut')
        size = holaf_lut_data.get('size')
        title = holaf_lut_data.get('title', 'Untitled Holaf LUT')

        if not isinstance(lut_np, np.ndarray) or not isinstance(size, int) or size == 0:
            print("[HolafLutSaver] Error: Malformed HOLAF_LUT_DATA content.")
            return {}
            
        now = datetime.datetime.now()

        # Format the subfolder and filename using strftime codes (e.g., %Y for year).
        # This allows for dynamic and organized file saving.
        try:
            formatted_subfolder = now.strftime(subfolder)
        except Exception:
            formatted_subfolder = subfolder # Fallback if format string is invalid.

        try:
            formatted_filename_base = now.strftime(filename)
        except Exception:
            formatted_filename_base = filename # Fallback if format string is invalid.

        # Construct the full output path and create the directory if it doesn't exist.
        output_path = os.path.join(_validate_lut_path(base_path), formatted_subfolder)
        os.makedirs(output_path, exist_ok=True)

        final_filepath, final_filename = self.get_unique_filepath(output_path, formatted_filename_base, ".cube")

        try:
            with open(final_filepath, 'w', encoding='utf-8') as f:
                # Write the standard .cube file header.
                f.write(f'TITLE "{title}"\n')
                f.write(f'LUT_3D_SIZE {size}\n\n')
                
                # Vectorized write: numpy C-order gives R-major (R changes fastest) automatically.
                lut_flat = lut_np.reshape(-1, 3)
                np.savetxt(f, lut_flat, fmt='%.6f %.6f %.6f')
            
        except Exception as e:
            print(f"[HolafLutSaver] Error writing .cube file to {final_filepath}: {e}")
            return {"ui": {"saved_luts": [{"filename": final_filename, "error": str(e)}]}}

        # Return a dictionary for the ComfyUI frontend to display feedback (e.g., the saved filename).
        return {"ui": {"saved_luts": [{"filename": final_filename}]}}