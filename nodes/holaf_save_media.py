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
import av

class HolafSaveMedia:
    """
    Unified node to save Images, Videos, and Audio.
    Supports optional inputs and multiplexing audio into video files.
    """
    def __init__(self):
        self.output_dir = folder_paths.get_output_directory()
        self.type = "output"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "mode": (["image", "video", "audio"], {"default": "image"}),
                
                "--- GENERIC SETTINGS ---": (["-----------------"],),
                "base_path": ("STRING", {"default": folder_paths.get_output_directory()}),
                "subfolder": ("STRING", {"default": "%Y-%m-%d"}),
                "filename": ("STRING", {"default": "%Y-%m-%d-%Hh%Mm%Ss"}),
                "save_prompt": ("BOOLEAN", {"default": True}),
                "save_workflow": ("BOOLEAN", {"default": True}),
                
                "--- IMAGE FORMAT ---": (["-----------------"],),
                "image_format": (["png", "jpg", "jpeg", "webp"], {"default": "png"}),
                "image_compression": ("INT", {"default": 4, "min": 1, "max": 9, "step": 1}), # PNG comp
                "image_quality": ("INT", {"default": 90, "min": 1, "max": 100, "step": 1}),  # JPG/WEBP
                
                "--- VIDEO FORMAT ---": (["-----------------"],),
                "video_container": (["mp4", "webm", "gif"], {"default": "mp4"}),
                "video_codec": (["auto", "h264", "h265", "vp9", "av1"], {"default": "auto"}),
                "video_fps": ("INT", {"default": 24, "min": 1, "max": 120, "step": 1}),
                "video_quality": ("INT", {"default": 23, "min": 0, "max": 63, "step": 1}),
                
                "--- AUDIO FORMAT ---": (["-----------------"],),
                "audio_format": (["wav", "mp3", "flac"], {"default": "wav"}),
                "audio_bitrate_kbps": ("INT", {"default": 192, "min": 64, "max": 320, "step": 32}),
            },
            "optional": {
                "image": ("IMAGE",),
                "audio": ("AUDIO",),
                "prompt": ("STRING", {"forceInput": True}), # forceInput removes the textbox and creates only a slot
            },
            "hidden": {
                "prompt_hidden": "PROMPT", 
                "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }

    RETURN_TYPES = ("IMAGE", "AUDIO", "STRING", "STRING", "STRING",)
    RETURN_NAMES = ("image", "audio", "filepath", "prompt", "workflow_json",)
    FUNCTION = "save_media"
    OUTPUT_NODE = True
    CATEGORY = "Holaf"

    def get_unique_filepath(self, directory, base_filename, ext):
        filepath = os.path.join(directory, f"{base_filename}{ext}")
        counter = 1
        while os.path.exists(filepath):
            filepath = os.path.join(directory, f"{base_filename}_{counter:04d}{ext}")
            counter += 1
        return filepath, os.path.basename(filepath)

    def _save_metadata(self, output_path, base_name, prompt, save_prompt, save_workflow, prompt_hidden, extra_pnginfo):
        workflow_json = ""
        
        # Save Prompt
        if save_prompt and prompt:
            prompt_path = os.path.join(output_path, f"{base_name}.txt")
            try:
                with open(prompt_path, 'w', encoding='utf-8') as f:
                    f.write(prompt)
            except Exception as e:
                print(f"[Holaf Save Media] Error saving prompt: {e}")

        # Save Workflow
        workflow_data = extra_pnginfo.get('workflow') if extra_pnginfo else prompt_hidden
        if workflow_data:
            try:
                workflow_json = json.dumps(workflow_data, indent=2)
            except Exception as e:
                workflow_json = json.dumps({"error": f"Failed to serialize workflow: {e}"})

        if save_workflow and workflow_json:
            workflow_path = os.path.join(output_path, f"{base_name}.json")
            try:
                with open(workflow_path, 'w', encoding='utf-8') as f:
                    f.write(workflow_json)
            except Exception as e:
                print(f"[Holaf Save Media] Error saving workflow: {e}")
                
        return workflow_json

    def _write_audio_to_stream(self, container, audio_stream, audio_np, sample_rate):
        """Safely writes a numpy audio array to a PyAV stream using a resampler and FIFO buffer."""
        channels, samples = audio_np.shape
        layout = 'stereo' if channels == 2 else 'mono'
        
        # Create a single logical frame from the numpy array
        frame = av.AudioFrame.from_ndarray(audio_np, format='fltp', layout=layout)
        frame.sample_rate = sample_rate
        
        # Resampler ensures format matches the codec's strict requirements
        resampler = av.AudioResampler(
            format=audio_stream.format, 
            layout=audio_stream.layout, 
            rate=audio_stream.rate
        )
        
        fifo = av.AudioFifo()
        
        # Push to FIFO
        for resampled_frame in resampler.resample(frame):
            fifo.write(resampled_frame)
        for resampled_frame in resampler.resample(None): # Flush
            fifo.write(resampled_frame)
            
        # Pull exactly what the codec needs
        frame_size = audio_stream.frame_size or 1024
        while fifo.samples >= frame_size:
            out_frame = fifo.read(frame_size)
            out_frame.pts = None # Let PyAV handle presentation timestamps
            for packet in audio_stream.encode(out_frame):
                container.mux(packet)
        
        # Pull remaining
        if fifo.samples > 0:
            out_frame = fifo.read(fifo.samples)
            out_frame.pts = None
            for packet in audio_stream.encode(out_frame):
                container.mux(packet)
                
        # Flush encoder
        for packet in audio_stream.encode(None):
            container.mux(packet)

    def save_media(self, mode, **kwargs):
        # 1. Parse Common Arguments
        base_path = kwargs.get("base_path", folder_paths.get_output_directory())
        subfolder = kwargs.get("subfolder", "%Y-%m-%d")
        filename = kwargs.get("filename", "%Y-%m-%d-%Hh%Mm%Ss")
        save_prompt = kwargs.get("save_prompt", True)
        save_workflow = kwargs.get("save_workflow", True)
        
        prompt = kwargs.get("prompt", "")
        prompt_hidden = kwargs.get("prompt_hidden", None)
        extra_pnginfo = kwargs.get("extra_pnginfo", None)
        
        image_tensor = kwargs.get("image", None)
        audio_data = kwargs.get("audio", None)

        # 2. Prepare Path
        now = datetime.datetime.now()
        try:
            formatted_subfolder = now.strftime(subfolder)
        except Exception:
            formatted_subfolder = now.strftime('%Y-%m-%d')
        try:
            formatted_filename_base = now.strftime(filename)
        except Exception:
            formatted_filename_base = now.strftime('%Y-%m-%d-%Hh%Mm%Ss')

        output_path = os.path.join(base_path, formatted_subfolder)
        os.makedirs(output_path, exist_ok=True)

        # 3. ROUTING LOGIC
        if mode == "image":
            if image_tensor is None:
                print("[Holaf Save Media] Warning: Mode is 'image' but no image provided.")
                return {"ui": {"text": ["No image provided"]}, "result": (image_tensor, audio_data, "", "", "")}
            
            img_format = kwargs.get("image_format", "png")
            ext = f".{img_format}"
            img_array = (image_tensor.cpu().numpy() * 255.0).astype(np.uint8)
            
            results = []
            workflow_json = ""
            final_path = ""
            
            for i in range(img_array.shape[0]):
                file_path, final_filename = self.get_unique_filepath(output_path, formatted_filename_base, ext)
                base_name = os.path.splitext(final_filename)[0]
                final_path = file_path
                
                img = Image.fromarray(img_array[i])
                try:
                    if img_format == "png":
                        img.save(file_path, compress_level=kwargs.get("image_compression", 4))
                    else:
                        img.save(file_path, quality=kwargs.get("image_quality", 90))
                        
                    results.append({"filename": final_filename, "subfolder": formatted_subfolder, "type": self.type})
                except Exception as e:
                     print(f"[Holaf Save Media] Error saving image: {e}")

                # Only save metadata once per batch (optimization)
                if i == 0:
                    workflow_json = self._save_metadata(output_path, base_name, prompt, save_prompt, save_workflow, prompt_hidden, extra_pnginfo)

            return {"ui": {"images": results}, "result": (image_tensor, audio_data, final_path, prompt, workflow_json)}


        elif mode == "video":
            if image_tensor is None:
                print("[Holaf Save Media] Warning: Mode is 'video' but no image provided.")
                return {"ui": {"text": ["No image provided"]}, "result": (image_tensor, audio_data, "", "", "")}

            v_container = kwargs.get("video_container", "mp4")
            v_codec_opt = kwargs.get("video_codec", "auto")
            v_fps = kwargs.get("video_fps", 24)
            v_quality = kwargs.get("video_quality", 23)

            # Determine Codec
            if v_container == "mp4":
                if v_codec_opt == "auto": v_codec = "libx264"
                elif v_codec_opt == "h265": v_codec = "libx265"
                else: v_codec = "libx264"
            elif v_container == "webm":
                if v_codec_opt == "auto": v_codec = "libvpx-vp9"
                elif v_codec_opt == "av1": v_codec = "libaom-av1"
                else: v_codec = "libvpx-vp9"
            elif v_container == "gif":
                v_codec = "gif"
            else:
                v_codec = "libx264"

            ext = f".{v_container}"
            video_path, final_video_filename = self.get_unique_filepath(output_path, formatted_filename_base, ext)
            base_name = os.path.splitext(final_video_filename)[0]

            img_array = (image_tensor.cpu().numpy() * 255.0).astype(np.uint8)
            batch_size, height, width, channels = img_array.shape
            
            input_pixel_format = 'rgba' if channels == 4 else 'gray' if channels == 1 else 'rgb24'

            try:
                container = av.open(video_path, mode='w')
            except Exception as e:
                print(f"[Holaf Save Media] Codec error ({v_codec}): {e}. Falling back.")
                v_codec = 'libx264' if v_container == 'mp4' else 'libvpx-vp9'
                container = av.open(video_path, mode='w')

            # Setup Video Stream
            v_stream = container.add_stream(v_codec, rate=v_fps)
            v_stream.width = width
            v_stream.height = height
            
            if v_codec == 'gif':
                 v_stream.pix_fmt = 'rgb24'
            else:
                v_stream.pix_fmt = 'yuv420p'
                v_stream.options = {'crf': str(v_quality)}

            # Write Video Frames
            for i in range(batch_size):
                frame_data = img_array[i]
                frame = av.VideoFrame.from_ndarray(frame_data, format=input_pixel_format)
                for packet in v_stream.encode(frame):
                    container.mux(packet)
            for packet in v_stream.encode():
                container.mux(packet)

            # Handle Audio Multiplexing
            if audio_data is not None and v_codec != 'gif':
                audio_tensor = audio_data.get("waveform")
                if audio_tensor is not None and audio_tensor.dim() >= 3:
                    sample_rate = audio_data.get("sample_rate", 44100)
                    # ComfyUI audio shape: [Batch, Channels, Samples]. Take first batch.
                    audio_np = audio_tensor[0].cpu().numpy().astype(np.float32)
                    
                    if audio_np.size > 0:
                        # Truncate audio to match video duration
                        video_duration_sec = batch_size / v_fps
                        max_samples = int(video_duration_sec * sample_rate)
                        if audio_np.shape[1] > max_samples:
                            audio_np = audio_np[:, :max_samples]

                        # Determine Audio Codec for muxing
                        a_codec = 'aac' if v_container == 'mp4' else 'libopus'
                        a_stream = container.add_stream(a_codec, rate=sample_rate)
                        a_bitrate = kwargs.get("audio_bitrate_kbps", 192) * 1000
                        a_stream.bit_rate = a_bitrate

                        self._write_audio_to_stream(container, a_stream, audio_np, sample_rate)

            container.close()
            workflow_json = self._save_metadata(output_path, base_name, prompt, save_prompt, save_workflow, prompt_hidden, extra_pnginfo)
            
            results = [{"filename": final_video_filename, "subfolder": formatted_subfolder, "type": self.type}]
            ui_key = v_container + "s" # e.g., "mp4s", "gifs"
            return {"ui": {ui_key: results}, "result": (image_tensor, audio_data, video_path, prompt, workflow_json)}


        elif mode == "audio":
            if audio_data is None:
                print("[Holaf Save Media] Warning: Mode is 'audio' but no audio provided.")
                return {"ui": {"text": ["No audio provided"]}, "result": (image_tensor, audio_data, "", "", "")}

            a_format = kwargs.get("audio_format", "wav")
            ext = f".{a_format}"
            audio_path, final_audio_filename = self.get_unique_filepath(output_path, formatted_filename_base, ext)
            base_name = os.path.splitext(final_audio_filename)[0]

            audio_tensor = audio_data.get("waveform")
            sample_rate = audio_data.get("sample_rate", 44100)

            if audio_tensor is not None and audio_tensor.dim() >= 3:
                audio_np = audio_tensor[0].cpu().numpy().astype(np.float32)
                
                if audio_np.size > 0:
                    container = av.open(audio_path, mode='w')
                    
                    if a_format == "wav":
                        a_codec = "pcm_s16le"
                    elif a_format == "mp3":
                        a_codec = "libmp3lame"
                    else: # flac
                        a_codec = "flac"
                        
                    a_stream = container.add_stream(a_codec, rate=sample_rate)
                    
                    if a_format != "wav":
                        a_stream.bit_rate = kwargs.get("audio_bitrate_kbps", 192) * 1000

                    self._write_audio_to_stream(container, a_stream, audio_np, sample_rate)
                    container.close()

            workflow_json = self._save_metadata(output_path, base_name, prompt, save_prompt, save_workflow, prompt_hidden, extra_pnginfo)
            
            results = [{"filename": final_audio_filename, "subfolder": formatted_subfolder, "type": self.type}]
            return {"ui": {"audios": results}, "result": (image_tensor, audio_data, audio_path, prompt, workflow_json)}

        return {"ui": {}, "result": (image_tensor, audio_data, "", "", "")}