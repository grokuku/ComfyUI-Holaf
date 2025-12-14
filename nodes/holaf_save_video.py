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
import folder_paths
import av

class HolafSaveVideo:
    """
    Saves a sequence of images (batch) as a video file using PyAV.
    Supports multiple codecs (h264, h265, vp9, av1) and GIF.
    Metadata (prompt/workflow) is saved ONLY in sidecar files (.txt/.json).
    """
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "images": ("IMAGE",),
                "fps": ("INT", {"default": 24, "min": 1, "max": 120, "step": 1}),
                "format": (["mp4 (h264)", "mp4 (h265)", "webm (vp9)", "webm (av1)", "gif"],),
                # Quality is essentially CRF (Constant Rate Factor).
                # Lower is better quality. Typical range 18-28.
                "quality": ("INT", {"default": 23, "min": 0, "max": 63, "step": 1}),
                
                "prompt": ("STRING", {"multiline": True, "default": ""}),
                # The root directory for saving files.
                "base_path": ("STRING", {"default": folder_paths.get_output_directory()}),
                # Subfolder within the base path; supports strftime date/time formatting.
                "subfolder": ("STRING", {"default": "%Y-%m-%d"}),
                # Filename pattern (without extension); supports strftime.
                "filename": ("STRING", {"default": "%Y-%m-%d-%Hh%Mm%Ss"}),
                "save_prompt": ("BOOLEAN", {"default": True}),
                "save_workflow": ("BOOLEAN", {"default": True}),
            },
            "hidden": {"prompt_hidden": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
        }

    RETURN_TYPES = ("STRING", "STRING", "STRING",)
    RETURN_NAMES = ("filename", "prompt", "workflow_json",)
    FUNCTION = "save_video"
    OUTPUT_NODE = True
    CATEGORY = "Holaf"

    def get_unique_filepath(self, directory, base_filename, ext):
        """
        Prevents overwriting files by appending a numeric suffix if the
        target filename already exists.
        """
        filepath = os.path.join(directory, f"{base_filename}{ext}")
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(directory, f"{base_filename}_{counter:04d}{ext}")
            counter += 1
        return filepath, os.path.basename(filepath)

    def save_video(self, images, fps, format, quality, prompt, base_path, subfolder, filename, save_prompt, save_workflow, prompt_hidden=None, extra_pnginfo=None):
        
        # --- 1. Parse Format & Codec ---
        # Map UI selection to (extension, pyav_codec_name)
        # Default fallback
        container_ext = "mp4"
        codec_name = "libx264"

        if "mp4" in format:
            container_ext = "mp4"
            if "h265" in format:
                codec_name = "libx265" # HEVC
            else:
                codec_name = "libx264" # Standard
        elif "webm" in format:
            container_ext = "webm"
            if "av1" in format:
                codec_name = "libaom-av1" # Modern, high efficiency, slow
            else:
                codec_name = "libvpx-vp9" # Standard for WebM
        elif format == "gif":
            container_ext = "gif"
            codec_name = "gif"

        # --- 2. Prepare Paths and Filenames ---
        now = datetime.datetime.now()
        
        try:
            formatted_subfolder = now.strftime(subfolder)
        except:
            formatted_subfolder = now.strftime('%Y-%m-%d')

        try:
            formatted_filename_base = now.strftime(filename)
        except:
            formatted_filename_base = now.strftime('%Y-%m-%d-%Hh%Mm%Ss')

        output_path = os.path.join(base_path, formatted_subfolder)
        os.makedirs(output_path, exist_ok=True)

        ext = f".{container_ext}"
        
        # Get unique output path
        video_path, final_video_filename = self.get_unique_filepath(output_path, formatted_filename_base, ext)
        final_filename_base = os.path.splitext(final_video_filename)[0]

        # --- 3. Prepare Video Encoding ---
        # Convert tensor batch (B,H,W,C) to numpy uint8
        img_array = (images.cpu().numpy() * 255.0).astype(np.uint8)
        batch_size, height, width, channels = img_array.shape

        # Detect input format based on channels (3=RGB, 4=RGBA)
        if channels == 4:
            input_pixel_format = 'rgba'
        elif channels == 1:
            input_pixel_format = 'gray'
        else:
            input_pixel_format = 'rgb24'

        # Setup PyAV container
        try:
            container = av.open(video_path, mode='w')
        except Exception as e:
            # Fallback if specific codec fails (e.g. h265 not installed), try safe default
            print(f"[Holaf Save Video] Error opening container with {codec_name}: {e}. Falling back to default.")
            codec_name = 'libx264' if container_ext == 'mp4' else 'libvpx-vp9'
            container = av.open(video_path, mode='w')

        stream = container.add_stream(codec_name, rate=fps)
        stream.width = width
        stream.height = height
        
        if codec_name == 'gif':
             stream.pix_fmt = 'rgb24'
        else:
            # For video codecs, yuv420p is the most compatible standard.
            stream.pix_fmt = 'yuv420p'
            stream.options = {'crf': str(quality)}

        # --- 4. Write Frames ---
        for i in range(batch_size):
            frame_data = img_array[i] # (H, W, C)
            frame = av.VideoFrame.from_ndarray(frame_data, format=input_pixel_format)
            
            for packet in stream.encode(frame):
                container.mux(packet)

        # Flush stream
        for packet in stream.encode():
            container.mux(packet)
            
        container.close()

        # --- 5. Handle Sidecar Files (Metadata) ---
        
        # Save Prompt (.txt)
        if save_prompt and prompt:
            prompt_path = os.path.join(output_path, f"{final_filename_base}.txt")
            try:
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(prompt)
            except Exception as e:
                print(f"[Holaf Save Video] Error saving prompt: {e}")

        # Serialize Workflow
        workflow_json = ""
        workflow_data_to_save = extra_pnginfo.get('workflow') if extra_pnginfo else prompt_hidden
        if workflow_data_to_save:
            try:
                workflow_json = json.dumps(workflow_data_to_save, indent=2)
            except Exception as e:
                workflow_json = json.dumps({"error": f"Failed to serialize workflow: {e}"})

        # Save Workflow (.json)
        if save_workflow and workflow_json:
            workflow_path = os.path.join(output_path, f"{final_filename_base}.json")
            try:
                with open(workflow_path, 'w', encoding='utf-8') as f:
                    f.write(workflow_json)
            except Exception as e:
                print(f"[Holaf Save Video] Error saving workflow: {e}")

        # --- 6. Return Results ---
        results = [{
            "filename": final_video_filename,
            "subfolder": formatted_subfolder,
            "type": self.type,
            "format": container_ext # Used by UI for icon/handling
        }]

        # "mp4s", "gifs" are common keys for UI preview in Comfy
        return {"ui": {container_ext + "s": results}, "result": (final_video_filename, prompt, workflow_json,)}