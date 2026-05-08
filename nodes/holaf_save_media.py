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
import time
import shutil
import tempfile
import datetime
import logging
import torch
import numpy as np
from PIL import Image
import folder_paths
import av

logger = logging.getLogger("Holaf.SaveMedia")

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
                "temp_dir": ("STRING", {"default": ""}),

                "--- IMAGE FORMAT ---": (["-----------------"],),
                "image_format": (["png", "jpg", "jpeg", "webp"], {"default": "png"}),
                "image_compression": ("INT", {"default": 4, "min": 1, "max": 9, "step": 1}), # PNG comp
                "image_quality": ("INT", {"default": 90, "min": 1, "max": 100, "step": 1}),  # JPG/WEBP

                "--- VIDEO FORMAT ---": (["-----------------"],),
                "video_container": (["mp4", "webm", "gif"], {"default": "mp4"}),
                "video_codec": (["auto", "h264", "h265", "vp9", "av1", "h264_nvenc", "hevc_nvenc"], {"default": "auto"}),
                "video_fps": ("INT", {"default": 24, "min": 1, "max": 120, "step": 1}),
                "video_quality": ("INT", {"default": 23, "min": 0, "max": 63, "step": 1}),

                "--- AUDIO FORMAT ---": (["-----------------"],),
                "audio_format": (["wav", "mp3", "flac"], {"default": "wav"}),
                "audio_bitrate_kbps": ("INT", {"default": 192, "min": 64, "max": 320, "step": 32}),
            },
            "optional": {
                "image": ("IMAGE",),
                "audio": ("AUDIO",),
                "prompt": ("STRING", {"forceInput": True}),
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

    @staticmethod
    def _validate_output_path(base_path, allowed_base=None):
        """Prevent path traversal by ensuring the resolved path stays within allowed_base."""
        if allowed_base is None:
            allowed_base = folder_paths.get_output_directory()
        abs_base = os.path.abspath(os.path.expanduser(base_path))
        abs_allowed = os.path.abspath(allowed_base)
        if not (abs_base == abs_allowed or abs_base.startswith(abs_allowed + os.sep)):
            logger.warning(f"base_path '{base_path}' resolves outside allowed directory '{allowed_base}'. Falling back.")
            return allowed_base
        return base_path

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
                logger.info(f"Error saving prompt: {e}")

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
                logger.info(f"Error saving workflow: {e}")

        return workflow_json

    def _write_audio_to_stream(self, container, audio_stream, audio_np, sample_rate):
        """Safely writes a numpy audio array to a PyAV stream."""
        channels, samples = audio_np.shape
        layout = 'stereo' if channels == 2 else 'mono'

        frame = av.AudioFrame.from_ndarray(audio_np, format='fltp', layout=layout)
        frame.sample_rate = sample_rate
        frame.pts = None # PyAV computes PTS automatically when None

        resampler = av.AudioResampler(
            format=audio_stream.format,
            layout=audio_stream.layout,
            rate=audio_stream.rate
        )

        fifo = av.AudioFifo()

        for resampled_frame in resampler.resample(frame):
            fifo.write(resampled_frame)
        for resampled_frame in resampler.resample(None): # Flush
            fifo.write(resampled_frame)

        frame_size = audio_stream.frame_size or 1024

        while fifo.samples >= frame_size:
            out_frame = fifo.read(frame_size)
            out_frame.pts = None
            for packet in audio_stream.encode(out_frame):
                container.mux(packet)

        if fifo.samples > 0:
            out_frame = fifo.read(fifo.samples)
            out_frame.pts = None
            for packet in audio_stream.encode(out_frame):
                container.mux(packet)

        # Flush encoder
        for packet in audio_stream.encode(None):
            container.mux(packet)

    @staticmethod
    def _detect_temp_dir():
        """Auto-detect the best temporary directory for encoding.
        Priority: /dev/shm (RAM disk) > system temp directory."""
        shm = "/dev/shm"
        if os.path.isdir(shm) and os.access(shm, os.W_OK):
            return shm
        return tempfile.gettempdir()

    @staticmethod
    def _is_codec_available(codec_name):
        """Check if a codec is available in PyAV/FFmpeg."""
        try:
            av.codec.Codec(codec_name, 'w')
            return True
        except ValueError:
            return False

    def _resolve_video_codec(self, container, codec_opt):
        """Resolve a user-friendly codec option to an internal FFmpeg codec name.
        Handles NVENC fallback gracefully."""
        if container == "gif":
            return "gif"

        if codec_opt in ("h264_nvenc", "hevc_nvenc"):
            if container != "mp4":
                logger.info(f"NVENC only works with MP4 container, falling back to auto for {container}.")
                return self._resolve_video_codec(container, "auto")
            if self._is_codec_available(codec_opt):
                return codec_opt
            fallback = "libx264" if codec_opt == "h264_nvenc" else "libx265"
            logger.info(f"{codec_opt} not available in PyAV, falling back to {fallback}.")
            return fallback

        if container == "mp4":
            if codec_opt in ("auto", "h264"):
                return "libx264"
            elif codec_opt == "h265":
                return "libx265"
            return "libx264"
        elif container == "webm":
            if codec_opt in ("auto", "vp9"):
                return "libvpx-vp9"
            elif codec_opt == "av1":
                return "libaom-av1"
            return "libvpx-vp9"
        return "libx264"

    def save_media(self, mode, **kwargs):
        t_total_start = time.time()

        def ts():
            """Return elapsed time since save started, formatted as [+X.XXs]."""
            return f"[+{time.time()-t_total_start:.2f}s]"

        # 1. Parse Common Arguments
        base_path_raw = kwargs.get("base_path", folder_paths.get_output_directory())
        base_path = self._validate_output_path(base_path_raw)
        subfolder = kwargs.get("subfolder", "%Y-%m-%d")
        filename = kwargs.get("filename", "%Y-%m-%d-%Hh%Mm%Ss")
        save_prompt = kwargs.get("save_prompt", True)
        save_workflow = kwargs.get("save_workflow", True)
        temp_dir_setting = kwargs.get("temp_dir", "")

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

        # Resolve temp directory for fast encoding
        if temp_dir_setting and temp_dir_setting.strip():
            temp_dir = temp_dir_setting.strip()
            if not (os.path.isdir(temp_dir) and os.access(temp_dir, os.W_OK)):
                logger.info(f"{ts()} temp_dir '{temp_dir}' not writable, auto-detecting.")
                temp_dir = self._detect_temp_dir()
        else:
            temp_dir = self._detect_temp_dir()
        logger.info(f"{ts()} Mode: {mode} | Temp: {temp_dir} | Output: {output_path}")

        # 3. ROUTING LOGIC
        if mode == "image":
            if image_tensor is None:
                logger.info(f"{ts()} Warning: Mode is 'image' but no image provided.")
                image_tensor = torch.zeros((1, 8, 8, 3))
                return {"ui": {"text": ["No image provided"]}, "result": (image_tensor, audio_data, "", "", "")}

            t0 = time.time()
            img_format = kwargs.get("image_format", "png")
            ext = f".{img_format}"
            img_cpu = image_tensor.cpu()
            img_array = img_cpu.float().mul(255).clamp(0, 255).byte().numpy()
            logger.info(f"{ts()} Tensor→numpy: {time.time()-t0:.2f}s")

            results = []
            workflow_json = ""
            final_path = ""

            total = img_array.shape[0]
            for i in range(total):
                t_img = time.time()
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
                     logger.info(f"{ts()} Error saving image {i}: {e}")

                if i == 0:
                    workflow_json = self._save_metadata(output_path, base_name, prompt, save_prompt, save_workflow, prompt_hidden, extra_pnginfo)

                if total <= 10 or (i + 1) % 10 == 0:
                    logger.info(f"{ts()} Image {i+1}/{total} saved in {time.time()-t_img:.2f}s")

            t_total = time.time() - t_total_start
            logger.info(f"{ts()} ═══ IMAGE DONE ═══ {t_total:.2f}s total | {total} images")
            return {"ui": {"images": results}, "result": (image_tensor, audio_data, final_path, prompt, workflow_json)}


        elif mode == "video":
            if image_tensor is None:
                logger.info(f"{ts()} Warning: Mode is 'video' but no image provided.")
                image_tensor = torch.zeros((1, 8, 8, 3))
                return {"ui": {"text": ["No image provided"]}, "result": (image_tensor, audio_data, "", "", "")}

            v_container = kwargs.get("video_container", "mp4")
            v_codec_opt = kwargs.get("video_codec", "auto")
            v_fps = kwargs.get("video_fps", 24)
            v_quality = kwargs.get("video_quality", 23)

            # Resolve codec (with NVENC support)
            v_codec = self._resolve_video_codec(v_container, v_codec_opt)
            is_nvenc = v_codec in ("h264_nvenc", "hevc_nvenc")
            enc_type = "GPU" if is_nvenc else "CPU"
            logger.info(f"{ts()} Codec: {v_codec} ({enc_type}) | {v_container} | {v_fps}fps | quality={v_quality}")

            ext = f".{v_container}"

            # Convert tensor using PyTorch CPU (SIMD-optimized) instead of numpy float16 (scalar-only)
            t0 = time.time()
            img_cpu = image_tensor.cpu()
            logger.info(f"{ts()} .cpu() transfer: {time.time()-t0:.3f}s")
            t0 = time.time()
            img_array = img_cpu.float().mul(255).clamp(0, 255).byte().numpy()
            batch_size, height, width, channels = img_array.shape
            logger.info(f"{ts()} torch→numpy: {time.time()-t0:.3f}s | {batch_size} frames, {width}x{height}")

            input_pixel_format = 'rgba' if channels == 4 else 'gray' if channels == 1 else 'rgb24'

            # --- CREATE TEMP FILE ---
            temp_video_path = None
            video_path = None
            try:
                try:
                    tmp_fd, temp_video_path = tempfile.mkstemp(suffix=ext, prefix='holaf_video_', dir=temp_dir)
                    os.close(tmp_fd)
                    logger.info(f"{ts()} Temp file: {temp_video_path}")
                except Exception as e:
                    logger.warning(f"{ts()} Temp file FAILED ({temp_dir}): {e}. Writing directly to output.")
                    video_path, final_video_filename = self.get_unique_filepath(output_path, formatted_filename_base, ext)
                    temp_video_path = video_path
                else:
                    video_path, final_video_filename = self.get_unique_filepath(output_path, formatted_filename_base, ext)

                base_name = os.path.splitext(final_video_filename)[0]

                # --- OPEN CONTAINER ---
                t0 = time.time()
                try:
                    container = av.open(temp_video_path, mode='w')
                except Exception as e:
                    if is_nvenc:
                        logger.info(f"{ts()} NVENC open FAILED: {e}. Fallback to CPU.")
                        v_codec = "libx264" if v_container == "mp4" else "libvpx-vp9"
                        is_nvenc = False
                        enc_type = "CPU"
                    else:
                        v_codec = 'libx264' if v_container == 'mp4' else 'libvpx-vp9'
                    container = av.open(temp_video_path, mode='w')
                logger.info(f"{ts()} Container opened ({v_codec}) in {time.time()-t0:.2f}s")

                # --- SETUP STREAMS ---
                t0 = time.time()
                v_stream = container.add_stream(v_codec, rate=v_fps)
                v_stream.width = width
                v_stream.height = height

                if v_codec == 'gif':
                    v_stream.pix_fmt = 'rgb24'
                else:
                    v_stream.pix_fmt = 'yuv420p'
                    if is_nvenc:
                        v_stream.options = {'preset': 'p4', 'cq': str(v_quality)}
                    else:
                        v_stream.options = {'crf': str(v_quality)}

                a_stream = None
                audio_np_truncated = None
                sample_rate = 44100

                if audio_data is not None and v_codec != 'gif':
                    audio_tensor = audio_data.get("waveform")
                    if audio_tensor is not None and audio_tensor.dim() >= 3:
                        sample_rate = audio_data.get("sample_rate", 44100)
                        audio_np_truncated = audio_tensor[0].cpu().numpy().astype(np.float32)

                        if audio_np_truncated.size > 0:
                            video_duration_sec = batch_size / v_fps
                            max_samples = int(video_duration_sec * sample_rate)
                            if audio_np_truncated.shape[1] > max_samples:
                                audio_np_truncated = audio_np_truncated[:, :max_samples]

                            a_codec = 'aac' if v_container == 'mp4' else 'libopus'
                            a_stream = container.add_stream(a_codec, rate=sample_rate)
                            a_bitrate = kwargs.get("audio_bitrate_kbps", 192) * 1000
                            a_stream.bit_rate = a_bitrate
                logger.info(f"{ts()} Streams setup: {time.time()-t0:.2f}s | audio={'yes' if a_stream else 'no'}")

                # --- WRITE VIDEO FRAMES ---
                t0 = time.time()
                t_last_report = t0
                for i in range(batch_size):
                    frame_data = img_array[i]
                    frame = av.VideoFrame.from_ndarray(frame_data, format=input_pixel_format)
                    for packet in v_stream.encode(frame):
                        container.mux(packet)

                    # Report timing every 10 frames
                    if (i + 1) % 10 == 0 or i == batch_size - 1:
                        now2 = time.time()
                        elapsed_segment = now2 - t_last_report
                        fps_segment = 10.0 / elapsed_segment if elapsed_segment > 0 else 0
                        logger.info(f"{ts()} Frames {max(1,i-8)}-{i+1}/{batch_size} | {elapsed_segment:.2f}s for 10 frames ({fps_segment:.1f} fps)")
                        t_last_report = now2

                for packet in v_stream.encode():
                    container.mux(packet)
                t_encode = time.time() - t0
                logger.info(f"{ts()} VIDEO ENCODE DONE: {t_encode:.2f}s total | avg {batch_size/t_encode:.1f} fps")

                # --- WRITE AUDIO ---
                if a_stream is not None and audio_np_truncated is not None:
                    t0 = time.time()
                    self._write_audio_to_stream(container, a_stream, audio_np_truncated, sample_rate)
                    logger.info(f"{ts()} Audio encode: {time.time()-t0:.2f}s")

                # --- CLOSE ---
                t0 = time.time()
                container.close()
                logger.info(f"{ts()} Container close: {time.time()-t0:.2f}s")

                # --- MOVE FROM TEMP TO FINAL ---
                if temp_video_path != video_path:
                    t0 = time.time()
                    try:
                        os.rename(temp_video_path, video_path)
                    except OSError:
                        shutil.move(temp_video_path, video_path)
                    mb = os.path.getsize(video_path) / (1024*1024)
                    logger.info(f"{ts()} File transfer: {mb:.1f} MB in {time.time()-t0:.2f}s")

                # --- SAVE METADATA ---
                t0 = time.time()
                workflow_json = self._save_metadata(output_path, base_name, prompt, save_prompt, save_workflow, prompt_hidden, extra_pnginfo)
                logger.info(f"{ts()} Metadata saved: {time.time()-t0:.2f}s")

                t_total = time.time() - t_total_start
                logger.info(f"{ts()} ═══ VIDEO DONE ═══ {t_total:.2f}s total | {final_video_filename}")
                results = [{"filename": final_video_filename, "subfolder": formatted_subfolder, "type": self.type}]
                ui_key = "gifs" if v_container == "gif" else "videos"
            finally:
                if temp_video_path and temp_video_path != video_path and os.path.exists(temp_video_path):
                    try:
                        os.unlink(temp_video_path)
                    except OSError:
                        pass
            return {"ui": {ui_key: results}, "result": (image_tensor, audio_data, video_path, prompt, workflow_json)}


        elif mode == "audio":
            if audio_data is None:
                logger.info(f"{ts()} Warning: Mode is 'audio' but no audio provided.")
                return {"ui": {"text": ["No audio provided"]}, "result": (image_tensor, audio_data, "", "", "")}

            a_format = kwargs.get("audio_format", "wav")
            ext = f".{a_format}"

            audio_tensor = audio_data.get("waveform")
            sample_rate = audio_data.get("sample_rate", 44100)

            t0 = time.time()
            if audio_tensor is not None and audio_tensor.dim() >= 3:
                audio_np = audio_tensor[0].cpu().numpy().astype(np.float32)
            else:
                audio_np = None
            logger.info(f"{ts()} Tensor→numpy: {time.time()-t0:.2f}s")

            temp_audio_path = None
            audio_path = None
            final_audio_filename = ""
            base_name = ""
            workflow_json = ""

            if audio_np is not None and audio_np.size > 0:
                try:
                    try:
                        tmp_fd, temp_audio_path = tempfile.mkstemp(suffix=ext, prefix='holaf_audio_', dir=temp_dir)
                        os.close(tmp_fd)
                    except Exception as e:
                        logger.warning(f"{ts()} Temp file FAILED: {e}. Writing directly.")
                        audio_path, final_audio_filename = self.get_unique_filepath(output_path, formatted_filename_base, ext)
                        temp_audio_path = audio_path
                    else:
                        audio_path, final_audio_filename = self.get_unique_filepath(output_path, formatted_filename_base, ext)

                    base_name = os.path.splitext(final_audio_filename)[0]

                    t0 = time.time()
                    container = av.open(temp_audio_path, mode='w')
                    
                    if a_format == "wav":
                        a_codec = "pcm_s16le"
                    elif a_format == "mp3":
                        a_codec = "libmp3lame"
                    else:
                        a_codec = "flac"
                        
                    a_stream = container.add_stream(a_codec, rate=sample_rate)
                    
                    if a_format != "wav":
                        a_stream.bit_rate = kwargs.get("audio_bitrate_kbps", 192) * 1000

                    self._write_audio_to_stream(container, a_stream, audio_np, sample_rate)
                    container.close()
                    logger.info(f"{ts()} Audio encode: {time.time()-t0:.2f}s")

                    if temp_audio_path != audio_path:
                        t0 = time.time()
                        try:
                            os.rename(temp_audio_path, audio_path)
                        except OSError:
                            shutil.move(temp_audio_path, audio_path)
                        mb = os.path.getsize(audio_path) / (1024*1024)
                        logger.info(f"{ts()} File transfer: {mb:.1f} MB in {time.time()-t0:.2f}s")
                finally:
                    if temp_audio_path and temp_audio_path != audio_path and os.path.exists(temp_audio_path):
                        try:
                            os.unlink(temp_audio_path)
                        except OSError:
                            pass
            else:
                audio_path = ""
                final_audio_filename = ""
                base_name = ""

            t0 = time.time()
            workflow_json = self._save_metadata(output_path, base_name, prompt, save_prompt, save_workflow, prompt_hidden, extra_pnginfo)
            logger.info(f"{ts()} Metadata saved: {time.time()-t0:.2f}s")
            
            t_total = time.time() - t_total_start
            logger.info(f"{ts()} ═══ AUDIO DONE ═══ {t_total:.2f}s total | {final_audio_filename}")
            results = [{"filename": final_audio_filename, "subfolder": formatted_subfolder, "type": self.type}]
            return {"ui": {"audios": results}, "result": (image_tensor, audio_data, audio_path, prompt, workflow_json)}

        logger.info(f"{ts()} ═══ NOTHING SAVED ═══ {time.time()-t_total_start:.2f}s total")
        return {"ui": {}, "result": (image_tensor, audio_data, "", "", "")}