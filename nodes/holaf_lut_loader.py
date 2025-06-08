import numpy as np
import os
import re
import folder_paths

# --- LUTs Folder Registration ---
# Add a dedicated 'luts' subfolder within the main 'models' directory for ComfyUI.
# This makes it easy for users to organize their .cube files.
luts_dir = os.path.join(folder_paths.models_dir, "luts")
if not os.path.exists(luts_dir):
    os.makedirs(luts_dir)
# Register this new path with ComfyUI's folder_paths system, allowing it
# to be recognized and used by functions like get_filename_list().
folder_paths.add_model_folder_path("luts", luts_dir)


class HolafLutLoader:
    """
    Loads a .cube LUT file from the `ComfyUI/models/luts` directory.
    It parses the file and provides the LUT data in a format ready for use
    by the HolafLutApplier node.
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        """
        Dynamically creates a dropdown menu in the UI populated with all
        files found in the 'models/luts' directory.
        """
        try:
            # Fetch the list of filenames from our registered 'luts' folder.
            lut_files = folder_paths.get_filename_list("luts")
        except:
            lut_files = []
            
        # Provide a fallback "None" option if no LUTs are found.
        if not lut_files:
            print("Warning: No LUT files found in the 'models/luts' directory.")
            lut_files.append("None")
        
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
        """
        Reads the selected .cube file, parses its contents, and returns the
        data in the standard HOLAF_LUT_DATA dictionary format.
        """
        # Handle cases where no LUT is selected.
        if not lut_name or lut_name == "None":
            # Return an empty but valid data structure to prevent errors in downstream nodes.
            return ({"lut": np.array([]), "size": 0, "title": "None"},)

        # Get the full, absolute path to the selected LUT file.
        lut_path = folder_paths.get_full_path("luts", lut_name)
        if not lut_path or not os.path.exists(lut_path):
            raise FileNotFoundError(f"LUT file '{lut_name}' not found at path: {lut_path}")
        
        title, size, lut_data_flat = "", 0, []
        
        try:
            with open(lut_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments.
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse metadata lines.
                    if line.startswith('TITLE'):
                        title = (re.findall(r'"([^"]*)"', line) or [""])[0]
                    elif line.startswith('LUT_3D_SIZE'):
                        size = int(line.split()[-1])
                    # Once size is known, start reading RGB data points.
                    elif size > 0:
                        values = [float(v) for v in line.split()]
                        if len(values) == 3:
                            lut_data_flat.append(values)
        except Exception as e:
            raise IOError(f"Error reading or parsing LUT file '{lut_name}': {e}")
        
        # Validate that the file was parsed correctly.
        if size == 0 or len(lut_data_flat) != size ** 3:
            raise ValueError(f"Failed to parse LUT '{lut_name}'. Check format. Expected {size**3} data points, found {len(lut_data_flat)}.")
            
        # Reshape the flat list of [R, G, B] values into a 3D LUT cube of shape (size, size, size, 3).
        # This is the format required for the trilinear interpolation in the applier node.
        lut_np = np.array(lut_data_flat, dtype=np.float32).reshape(size, size, size, 3)

        # Package the data into the standard dictionary format.
        holaf_lut_data = {
            "lut": lut_np,
            "size": size,
            "title": title if title else os.path.splitext(lut_name)[0]
        }
        
        return (holaf_lut_data,)