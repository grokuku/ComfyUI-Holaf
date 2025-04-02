import torch
import time
import csv
import os
import folder_paths
import comfy.samplers
import comfy.sample
import comfy.model_management
# import comfy.model_patcher # Not needed
# import comfy.sd # Not needed here
import nodes as comfy_nodes
import platform
import math
import io
import csv
import re
import os
import traceback # Import traceback for detailed error logging

# Attempt to import psutil, handle if not found
try:
    import psutil
    psutil_available = True
except ImportError:
    psutil_available = False
    print("[HolafBenchmarkRunner] Warning: 'psutil' library not found. CPU/RAM details will be limited. Install with 'pip install psutil'.")

# ==================================================================================
# HolafBenchmarkRunner Node - Documentation
# ==================================================================================
# Author: Cline (AI Assistant) for Holaf
# Date: 2025-04-02 (Updated)
# Purpose: Benchmarks SD models. FLUX UNet benchmarking is currently unsupported due to internal sampling complexities.
# How it works: Iterates SD models/resolutions, uses KSampler. Logs errors for FLUX UNets.
# Inputs: holaf_model_info_list, resolutions, steps, sampler_name, scheduler
# Outputs: report_text (CSV string)
# Dependencies: standard libs, psutil (optional), ComfyUI modules
# ==================================================================================

class HolafBenchmarkRunner:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "holaf_model_info_list": ("HOLAF_MODEL_INFO_LIST",),
                "resolutions": ("STRING", {"default": "512, 768-1024:128", "multiline": False}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS, ),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, ),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("report_text",)
    FUNCTION = "run_benchmark"
    CATEGORY = "Holaf"

    def parse_resolutions(self, resolutions_string):
        final_resolutions = set()
        parts = resolutions_string.split(',')
        range_pattern = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*:\s*(\d+)\s*$")
        for part in parts:
            part = part.strip()
            if not part: continue
            match = range_pattern.match(part)
            if match:
                try:
                    start, end, step = map(int, match.groups())
                    if start <= end and step > 0:
                        current_res = start
                        while current_res <= end: final_resolutions.add(current_res); current_res += step
                        if end > start and end not in final_resolutions and (end > (current_res - step) if current_res > start else True): final_resolutions.add(end)
                    else: print(f"[HolafBenchmarkRunner] Warning: Invalid range values in '{part}'.")
                except ValueError: print(f"[HolafBenchmarkRunner] Warning: Invalid numeric format in range '{part}'.")
            else:
                try:
                    res_val = int(part)
                    if res_val > 0: final_resolutions.add(res_val)
                    else: print(f"[HolafBenchmarkRunner] Warning: Ignoring non-positive resolution '{part}'.")
                except ValueError: print(f"[HolafBenchmarkRunner] Warning: Invalid format for resolution or range '{part}'.")
        if not final_resolutions: print(f"[HolafBenchmarkRunner] Warning: No valid resolutions parsed from '{resolutions_string}'."); return []
        valid_resolutions = {res for res in final_resolutions if res % 8 == 0}
        if len(valid_resolutions) != len(final_resolutions): print(f"[HolafBenchmarkRunner] Warning: Removed resolutions not divisible by 8.")
        unique_sorted_resolutions = sorted(list(valid_resolutions))
        print(f"[HolafBenchmarkRunner] Final resolutions to test: {unique_sorted_resolutions}")
        return unique_sorted_resolutions

    def _bytes_to_gb(self, b):
        if b is None or b == 0: return 0.0
        return round(b / (1024**3), 2)

    def _infer_model_family(self, model_name): # Only used for SD conditioning logic now
        if not model_name: return "Unknown"
        name_lower = model_name.lower()
        if "sdxl" in name_lower or "sd_xl" in name_lower: return "SDXL"
        elif "sd15" in name_lower or "sd_15" in name_lower or "v1-5" in name_lower: return "SD1.5"
        elif "sd21" in name_lower or "sd_21" in name_lower or "v2-1" in name_lower: return "SD2.1"
        elif "sd2" in name_lower or "sd_2" in name_lower or "v2-0" in name_lower: return "SD2.0"
        else: return "Unknown" # Simplified

    def _get_system_info_only(self):
        info = {"cpu": "N/A", "ram_gb": "N/A", "gpu": "N/A", "gpu_mem_gb": "N/A", "os": "N/A"}
        try: info["os"] = f"{platform.system()} {platform.release()}"
        except Exception: pass # Ignore errors here
        try:
            cpu_name = platform.processor() if hasattr(platform, 'processor') and platform.processor() else platform.machine()
            cpu_cores = psutil.cpu_count(logical=True) if psutil_available else '?'
            info["cpu"] = f"{cpu_name} ({cpu_cores} cores)"
        except Exception: pass
        try:
            if psutil_available: info["ram_gb"] = self._bytes_to_gb(psutil.virtual_memory().total)
            else: info["ram_gb"] = "N/A (psutil missing)"
        except Exception: pass
        try:
            if torch.cuda.is_available():
                gpu_id = torch.cuda.current_device(); info["gpu"] = torch.cuda.get_device_name(gpu_id)
                props = torch.cuda.get_device_properties(gpu_id); info["gpu_mem_gb"] = self._bytes_to_gb(props.total_memory)
            else: info["gpu"] = "No CUDA GPU detected"; info["gpu_mem_gb"] = 0.0
        except Exception: info["gpu"] = "Error detecting GPU"; info["gpu_mem_gb"] = "Error"
        print(f"[HolafBenchmarkRunner] System Info: OS={info['os']}, CPU={info['cpu']}, RAM={info['ram_gb']}GB, GPU={info['gpu']} ({info['gpu_mem_gb']}GB)")
        return info

    def run_benchmark(self, holaf_model_info_list, resolutions, steps, sampler_name, scheduler):
        if not isinstance(holaf_model_info_list, list) or not holaf_model_info_list:
            print(f"[HolafBenchmarkRunner] Error: Invalid input type or empty list for holaf_model_info_list.")
            return ("",)

        parsed_resolutions = self.parse_resolutions(resolutions)
        if not parsed_resolutions: return ("",)

        system_info_dict = self._get_system_info_only()
        results_data = []
        header = ["Resolution", "Steps", "Sampler", "Scheduler", "Time (s)", "Pixels/s", "Model Name", "Model Type", "CPU", "RAM (GB)", "GPU", "GPU Memory (GB)", "OS"]
        results_data.append(header)

        device = comfy.model_management.get_torch_device()
        batch_size = 1
        overall_start_time = time.perf_counter()

        for model_index, model_info in enumerate(holaf_model_info_list):
            if not isinstance(model_info, dict) or not all(k in model_info for k in ['model', 'name', 'type']):
                print(f"[HolafBenchmarkRunner] Warning: Skipping invalid item in input list at index {model_index}.")
                continue

            model_object = model_info['model']
            model_name = model_info['name']
            model_type = model_info['type']

            if model_object is None: print(f"[HolafBenchmarkRunner] Warning: Skipping benchmark for '{model_name}' due to None model object."); continue
            if not model_name or not isinstance(model_name, str): model_name = f"Unknown Model {model_index+1} ({model_type})"

            print(f"\n[HolafBenchmarkRunner] === Starting Benchmark for Model {model_index+1}: {model_name} (Type: {model_type}) ===")
            model_start_time = time.perf_counter()

            # Skip FLUX models entirely for now, as direct sampling is problematic
            if model_type == 'FLUX':
                print(f"[HolafBenchmarkRunner] Warning: Benchmarking raw FLUX UNets is currently unsupported with this method. Skipping '{model_name}'.")
                # Add error rows for each resolution for this FLUX model
                for res in parsed_resolutions:
                    error_row = [f"{res}x{res}", steps, sampler_name, scheduler, "Unsupported", "Error", model_name, model_type, system_info_dict["cpu"], system_info_dict["ram_gb"], system_info_dict["gpu"], system_info_dict["gpu_mem_gb"], system_info_dict["os"]]
                    results_data.append(error_row)
                continue # Skip to the next model in the list

            # Proceed only for SD models
            for i, res in enumerate(parsed_resolutions):
                width = res; height = res
                latent_height = max(1, height // 8); latent_width = max(1, width // 8)
                latent_image = torch.zeros([batch_size, 4, latent_height, latent_width], device=device)
                print(f"[HolafBenchmarkRunner] ({i+1}/{len(parsed_resolutions)}) Testing resolution: {width}x{height} for '{model_name}'")

                positive_cond, negative_cond = None, None
                sampler_instance = None

                try: # Try block for SD conditioning and sampler prep
                    model_family = self._infer_model_family(model_name)
                    cond_dim = 768; pooled_dim = 1280
                    if model_family == "SDXL": cond_dim = 2048
                    else: # Try inferring non-SDXL cond dim
                        try:
                            inferred_cond_dim = cond_dim
                            if hasattr(model_object, 'model') and hasattr(model_object.model, 'token_embedding') and hasattr(model_object.model.token_embedding, 'weight'):
                                inferred_cond_dim = model_object.model.token_embedding.weight.shape[-1]
                            elif hasattr(model_object, 'model') and hasattr(model_object.model, 'embedding_dim'):
                                inferred_cond_dim = model_object.model.embedding_dim
                            if inferred_cond_dim != cond_dim: cond_dim = inferred_cond_dim
                        except Exception: pass # Ignore inference errors

                    cond_dict = {}
                    if model_family == "SDXL":
                        cond_dict = {"pooled_output": torch.zeros([batch_size, pooled_dim], device=device), "width": width, "height": height, "target_width": width, "target_height": height}
                    positive_cond = [[torch.zeros([batch_size, 77, cond_dim], device=device), cond_dict]]
                    negative_cond = [[torch.zeros([batch_size, 77, cond_dim], device=device), cond_dict]]

                    # Initialize KSampler for SD
                    current_model_options = getattr(model_object, 'model_options', {})
                    sampler_instance = comfy.samplers.KSampler(model=model_object, steps=steps, device=device, sampler=sampler_name, scheduler=scheduler, denoise=1.0, model_options=current_model_options)

                except Exception as e_prep:
                     print(f"[HolafBenchmarkRunner] Error preparing conditioning/sampler for SD model '{model_name}': {e_prep}")
                     print("--- Preparation Traceback ---"); print(traceback.format_exc()); print("---------------------------")
                     error_row = [f"{res}x{res}", steps, sampler_name, scheduler, "Prep Error", "Error", model_name, model_type, system_info_dict["cpu"], system_info_dict["ram_gb"], system_info_dict["gpu"], system_info_dict["gpu_mem_gb"], system_info_dict["os"]]
                     results_data.append(error_row)
                     continue # Skip to next resolution

                # --- Run the sampling process and time it ---
                comfy.model_management.throw_exception_if_processing_interrupted()
                start_time = time.perf_counter()
                try: # Try block for the actual sampling call
                    seed = 0; cfg = 1.0; disable_pbar = True
                    noise = comfy.sample.prepare_noise(latent_image, seed)

                    if sampler_instance is None: raise RuntimeError("KSampler not initialized for SD model.")
                    _ = sampler_instance.sample(noise=noise, positive=positive_cond, negative=negative_cond, cfg=cfg, latent_image=latent_image, start_step=0, last_step=steps, force_full_denoise=False, denoise_mask=None, sigmas=None, callback=None, disable_pbar=disable_pbar, seed=seed)

                except Exception as e_sample:
                    end_time = time.perf_counter()
                    duration = end_time - start_time
                    print(f"[HolafBenchmarkRunner] Error during sampling for {res}x{res} with model '{model_name}' ({model_type}): {e_sample}")
                    print("--- Sampling Traceback ---"); print(traceback.format_exc()); print("------------------------")
                    error_row = [f"{res}x{res}", steps, sampler_name, scheduler, f"Sample Error ({duration:.3f}s)", "Error", model_name, model_type, system_info_dict["cpu"], system_info_dict["ram_gb"], system_info_dict["gpu"], system_info_dict["gpu_mem_gb"], system_info_dict["os"]]
                    results_data.append(error_row)
                    continue # Skip to next resolution

                end_time = time.perf_counter()
                duration = end_time - start_time
                pixels = width * height
                pixels_per_second = pixels / duration if duration > 0 else 0
                print(f"[HolafBenchmarkRunner] Resolution {width}x{height} took {duration:.3f} seconds ({pixels_per_second:.2f} Pixels/s) for '{model_name}' ({model_type})")
                results_row = [f"{res}x{res}", steps, sampler_name, scheduler, f"{duration:.3f}", f"{pixels_per_second:.2f}", model_name, model_type, system_info_dict["cpu"], system_info_dict["ram_gb"], system_info_dict["gpu"], system_info_dict["gpu_mem_gb"], system_info_dict["os"]]
                results_data.append(results_row)

            model_end_time = time.perf_counter()
            print(f"[HolafBenchmarkRunner] === Benchmark for Model {model_index+1}: {model_name} ({model_type}) finished in {model_end_time - model_start_time:.3f} seconds ===")
        # --- End loop for models/UNets ---

        overall_end_time = time.perf_counter()
        print(f"\n[HolafBenchmarkRunner] All benchmarks finished in {overall_end_time - overall_start_time:.3f} seconds.")

        output_string = io.StringIO()
        writer = csv.writer(output_string)
        writer.writerows(results_data)
        report_text = output_string.getvalue()
        output_string.close()
        return (report_text,)

# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "HolafBenchmarkRunner": HolafBenchmarkRunner
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafBenchmarkRunner": "Benchmark Runner (Holaf)"
}
