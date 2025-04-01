import torch
import time
import csv
import os
import folder_paths
import comfy.samplers
import comfy.sample
import comfy.model_management
# import comfy.sd # No longer needed here
import nodes as comfy_nodes # Import the nodes module to potentially reuse EmptyLatentImage logic
import platform
import math
import io
import csv
import re # For parsing resolutions
import os # For basename

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
#
# Author: Cline (AI Assistant) for Holaf
# Date: 2025-04-01
#
# Purpose:
# This node performs a series of simplified sampling runs at different square resolutions
# to benchmark the pixel generation speed (pixels per second) of the hardware
# for a given sampler, scheduler, and step count. It avoids loading full models
# or complex conditioning to focus purely on the sampler's computational cost.
#
# How it works:
# 1. Takes a list of resolutions (e.g., "512, 768, 1024") or a range (e.g., "512-1024-128").
# 2. Takes sampler settings (steps, sampler name, scheduler name).
# 3. On trigger, iterates through each specified resolution.
# 4. For each resolution:
#    - Creates an empty latent tensor of the target size.
#    - Records the start time.
#    - Executes the core sampling loop using `comfy.sample.sample` with minimal inputs.
#      (Note: This still requires some form of model placeholder for the function signature,
#       but we aim to use a minimal/dummy one if possible, or handle potential errors
#       if a real model is strictly required by the chosen sampler internally).
#    - Records the end time.
#    - Calculates duration and pixels per second.
# 5. Collects system information (OS, CPU, RAM, GPU) and model details (name, inferred family).
# 6. Saves all results (Resolution, Steps, Sampler, Scheduler, Time (s), Pixels/s,
#    Model Name, Model Family, CPU, RAM (GB), GPU, GPU Memory (GB), OS)
#    to a CSV string.
# 7. Returns the generated CSV data as a string, containing results for one or both models.
#
# Inputs:
# - holaf_model_info_list (HOLAF_MODEL_INFO_LIST): A list containing one or two tuples.
#   Each tuple is (model_object, ckpt_name_string) (from HolafBenchmarkLoader).
# - resolutions (STRING): Comma-separated list of resolutions and/or ranges.
#   Examples: "512, 1024", "512-1024:128", "512, 768-1024:128, 2048"
#   Range format: "start-end:step". Step is required.
# - steps (INT): Number of sampling steps.
# - sampler_name (COMBO): The sampler to use.
# - scheduler (COMBO): The scheduler to use.
#
# Outputs:
# - report_text (STRING): The benchmark results formatted as a CSV string, including system and model info.
#
# Dependencies:
# - Requires standard Python libraries (time, csv, os, platform, math, io, re).
# - Requires `psutil` for detailed CPU/RAM info (optional, provides limited info otherwise).
# - Relies on ComfyUI's internal modules (torch, folder_paths, comfy.samplers, comfy.sample, comfy.model_management).
#
# ==================================================================================

class HolafBenchmarkRunner:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "holaf_model_info_list": ("HOLAF_MODEL_INFO_LIST",), # Takes the custom list input type
                "resolutions": ("STRING", {"default": "512, 768-1024:128", "multiline": False}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS, ),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, ),
                # Removed trigger input
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("report_text",) # Changed output name
    FUNCTION = "run_benchmark"
    CATEGORY = "Holaf"

    def parse_resolutions(self, resolutions_string):
        """ Parses a combined string of resolutions and ranges (e.g., "512, 768-1024:128"). """
        final_resolutions = set() # Use a set to automatically handle duplicates
        parts = resolutions_string.split(',')

        range_pattern = re.compile(r"^\s*(\d+)\s*-\s*(\d+)\s*:\s*(\d+)\s*$") # Pattern for "start-end:step"

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Check if it's a range
            match = range_pattern.match(part)
            if match:
                try:
                    start, end, step = map(int, match.groups())
                    if start <= end and step > 0:
                        # Generate resolutions in the range
                        current_res = start
                        while current_res <= end:
                            final_resolutions.add(current_res)
                            current_res += step
                        # Ensure the exact end is included if the step didn't land on it
                        # (Only add if it's greater than the last step-generated value)
                        if end > start and end not in final_resolutions and (end > (current_res - step) if current_res > start else True) :
                             final_resolutions.add(end)
                        print(f"[HolafBenchmarkRunner] Parsed range '{part}': Added {list(range(start, end + 1, step))}") # Approximate log
                    else:
                        print(f"[HolafBenchmarkRunner] Warning: Invalid range values in '{part}'. Ensure start <= end and step > 0.")
                except ValueError:
                    print(f"[HolafBenchmarkRunner] Warning: Invalid numeric format in range '{part}'.")
            else:
                # Assume it's a single resolution
                try:
                    res_val = int(part)
                    if res_val > 0:
                        final_resolutions.add(res_val)
                        print(f"[HolafBenchmarkRunner] Parsed single resolution: {res_val}")
                    else:
                        print(f"[HolafBenchmarkRunner] Warning: Ignoring non-positive resolution '{part}'.")
                except ValueError:
                    print(f"[HolafBenchmarkRunner] Warning: Invalid format for resolution or range '{part}'. Please use numbers or 'start-end:step'.")

        if not final_resolutions:
             print(f"[HolafBenchmarkRunner] Warning: No valid resolutions parsed from '{resolutions_string}'.")
             return []

        # Ensure resolutions are positive (already handled above) and reasonable (e.g., multiple of 8?)
        # Let's add a check for multiple of 8, common for latents
        valid_resolutions = {res for res in final_resolutions if res % 8 == 0}
        if len(valid_resolutions) != len(final_resolutions):
             print(f"[HolafBenchmarkRunner] Warning: Removed resolutions not divisible by 8.")

        # Sort the final set
        unique_sorted_resolutions = sorted(list(valid_resolutions))
        print(f"[HolafBenchmarkRunner] Final resolutions to test: {unique_sorted_resolutions}")
        return unique_sorted_resolutions

    def _bytes_to_gb(self, b):
        """Converts bytes to gigabytes."""
        if b is None or b == 0:
            return 0.0
        return round(b / (1024**3), 2)

    def _infer_model_family(self, model_name):
        """Attempts to infer model family from its name."""
        if not model_name:
            return "Unknown"
        name_lower = model_name.lower()
        if "sdxl" in name_lower or "sd_xl" in name_lower:
            return "SDXL"
        elif "sd15" in name_lower or "sd_15" in name_lower or "v1-5" in name_lower:
             # Check for specific SD1.5 variants before general SD1.5
             if "inpainting" in name_lower:
                 return "SD1.5-Inpainting"
             else:
                 return "SD1.5"
        elif "sd21" in name_lower or "sd_21" in name_lower or "v2-1" in name_lower:
             return "SD2.1"
        elif "sd2" in name_lower or "sd_2" in name_lower or "v2-0" in name_lower: # Check after 2.1
             return "SD2.0"
        elif "turbo" in name_lower:
             return "Turbo" # Could be SDXL Turbo or SD Turbo
        elif "lcm" in name_lower:
             return "LCM"
        elif "pony" in name_lower:
             return "Pony"
        # Add more rules as needed
        else:
            return "Unknown" # Default if no keywords match

    def _get_system_and_model_info(self, ckpt_name):
        """Collects system and model information based on checkpoint name."""
        info = {
            "model_name": ckpt_name if ckpt_name else "N/A",
            "model_family": "N/A",
            "cpu": "N/A",
            "ram_gb": "N/A",
            "gpu": "N/A",
            "gpu_mem_gb": "N/A",
            "os": "N/A",
        }

        # --- Model Info (derived from ckpt_name) ---
        info["model_family"] = self._infer_model_family(info["model_name"])

        # --- System Info ---
        try:
            info["os"] = f"{platform.system()} {platform.release()}"
        except Exception as e:
            print(f"[HolafBenchmarkRunner] Warning: Error getting OS info: {e}")

        try:
            cpu_name = platform.processor() if hasattr(platform, 'processor') and platform.processor() else platform.machine()
            cpu_cores = psutil.cpu_count(logical=True) if psutil_available else '?'
            info["cpu"] = f"{cpu_name} ({cpu_cores} cores)"
        except Exception as e:
            print(f"[HolafBenchmarkRunner] Warning: Error getting CPU info: {e}")

        try:
            if psutil_available:
                mem = psutil.virtual_memory()
                info["ram_gb"] = self._bytes_to_gb(mem.total)
            else:
                info["ram_gb"] = "N/A (psutil missing)"
        except Exception as e:
            print(f"[HolafBenchmarkRunner] Warning: Error getting RAM info: {e}")

        try:
            if torch.cuda.is_available():
                gpu_id = torch.cuda.current_device()
                info["gpu"] = torch.cuda.get_device_name(gpu_id)
                props = torch.cuda.get_device_properties(gpu_id)
                info["gpu_mem_gb"] = self._bytes_to_gb(props.total_memory)
            else:
                info["gpu"] = "No CUDA GPU detected"
                info["gpu_mem_gb"] = 0.0
        except Exception as e:
            print(f"[HolafBenchmarkRunner] Warning: Error getting GPU info: {e}")
            info["gpu"] = "Error detecting GPU"
            info["gpu_mem_gb"] = "Error"

        print(f"[HolafBenchmarkRunner] System Info: OS={info['os']}, CPU={info['cpu']}, RAM={info['ram_gb']}GB, GPU={info['gpu']} ({info['gpu_mem_gb']}GB)")
        print(f"[HolafBenchmarkRunner] Model Info: Name={info['model_name']}, Family={info['model_family']}")
        return info

    # Changed signature: takes the list of model info tuples
    def run_benchmark(self, holaf_model_info_list, resolutions, steps, sampler_name, scheduler):
        # --- Validate Input List ---
        if not isinstance(holaf_model_info_list, list) or not holaf_model_info_list:
            print(f"[HolafBenchmarkRunner] Error: Invalid input type or empty list for holaf_model_info_list. Expected list of tuples. Got: {type(holaf_model_info_list)}")
            return ("",)

        # --- Parse Resolutions (once) ---
        parsed_resolutions = self.parse_resolutions(resolutions)
        if not parsed_resolutions:
            print("[HolafBenchmarkRunner] Error: No valid resolutions to test.")
            return ("",) # Return empty string on error

        # --- Collect System Info Once ---
        # We get model info inside the loop now, but system info is constant
        # Need a dummy ckpt_name just to call the function structure
        # Or better, refactor _get_system_and_model_info
        # Let's refactor: separate system info collection
        system_info_dict = self._get_system_info_only()

        results_data = []
        # Header for CSV data - Extended
        header = [
            "Resolution", "Steps", "Sampler", "Scheduler", "Time (s)", "Pixels/s",
            "Model Name", "Model Family", "CPU", "RAM (GB)", "GPU", "GPU Memory (GB)", "OS"
        ]
        results_data.append(header) # Add header once

        device = comfy.model_management.get_torch_device()
        batch_size = 1
        overall_start_time = time.perf_counter()

        # --- Loop through each model provided ---
        for model_index, model_info_tuple in enumerate(holaf_model_info_list):

            if not isinstance(model_info_tuple, tuple) or len(model_info_tuple) != 2:
                print(f"[HolafBenchmarkRunner] Warning: Skipping invalid item in input list at index {model_index}. Expected tuple(model, ckpt_name).")
                continue

            model, ckpt_name = model_info_tuple

            # Validate model and name again inside the loop
            if model is None:
                 print(f"[HolafBenchmarkRunner] Warning: Skipping benchmark for item at index {model_index} due to None model object.")
                 continue
            if not ckpt_name or not isinstance(ckpt_name, str):
                 print(f"[HolafBenchmarkRunner] Warning: Invalid ckpt_name ('{ckpt_name}') for item at index {model_index}. Using placeholder.")
                 ckpt_name = f"Unknown Model {model_index+1}"

            print(f"\n[HolafBenchmarkRunner] === Starting Benchmark for Model {model_index+1}: {ckpt_name} ===")

            # --- Get Model Specific Info ---
            model_family = self._infer_model_family(ckpt_name)
            print(f"[HolafBenchmarkRunner] Model Info: Name={ckpt_name}, Family={model_family}")

            # --- Prepare inputs for comfy.sample.sample (potentially model-specific) ---
            # Determine conditioning dimension and pooled dimension based on model family
            cond_dim = 768 # Default SD1.5/SD2
            pooled_dim = 1280 # Default SDXL pooled output dimension

            if model_family == "SDXL":
                cond_dim = 2048 # Explicitly set for SDXL
                # pooled_dim remains 1280 (default for SDXL base)
                print(f"[HolafBenchmarkRunner] Setting cond_dim={cond_dim} and pooled_dim={pooled_dim} for SDXL family.")
            else:
                # Try to infer for non-SDXL models if needed, but 768 is usually correct
                try:
                    inferred_cond_dim = cond_dim # Start with default
                    if hasattr(model, 'model') and hasattr(model.model, 'token_embedding') and hasattr(model.model.token_embedding, 'weight'):
                        inferred_cond_dim = model.model.token_embedding.weight.shape[-1]
                        print(f"[HolafBenchmarkRunner] Attempted inference via token_embedding for non-SDXL: {inferred_cond_dim}")
                    elif hasattr(model, 'model') and hasattr(model.model, 'embedding_dim'):
                         inferred_cond_dim = model.model.embedding_dim
                         print(f"[HolafBenchmarkRunner] Attempted inference via embedding_dim attribute for non-SDXL: {inferred_cond_dim}")

                    if inferred_cond_dim != cond_dim:
                         print(f"[HolafBenchmarkRunner] Updating cond_dim for non-SDXL model to inferred value: {inferred_cond_dim}")
                         cond_dim = inferred_cond_dim
                    else:
                         print(f"[HolafBenchmarkRunner] Using default cond_dim ({cond_dim}) for non-SDXL model.")

                except Exception as e:
                    print(f"[HolafBenchmarkRunner] Error inferring cond_dim for non-SDXL, using default {cond_dim}: {e}")


            model_start_time = time.perf_counter()

            # --- Loop through resolutions for the current model ---
            for i, res in enumerate(parsed_resolutions):
                width = res
                height = res
                latent_height = max(1, height // 8)
                latent_width = max(1, width // 8)
                latent_image = torch.zeros([batch_size, 4, latent_height, latent_width], device=device)

                print(f"[HolafBenchmarkRunner] ({i+1}/{len(parsed_resolutions)}) Testing resolution: {width}x{height} for '{ckpt_name}'")

                # --- Create model-specific conditioning ---
                cond_dict = {}
                if model_family == "SDXL":
                    cond_dict = {
                        "pooled_output": torch.zeros([batch_size, pooled_dim], device=device),
                        "width": width,
                        "height": height,
                        "target_width": width, # Use benchmark resolution for target
                        "target_height": height # Use benchmark resolution for target
                    }
                    print(f"[HolafBenchmarkRunner] Using SDXL conditioning dict for {width}x{height}")
                else:
                    # For non-SDXL models, the dict remains empty
                    pass

                # Create the final conditioning structures
                positive_cond = [[torch.zeros([batch_size, 77, cond_dim], device=device), cond_dict]]
                negative_cond = [[torch.zeros([batch_size, 77, cond_dim], device=device), cond_dict]]

                # Initialize KSampler for the current model
                try:
                     sampler = comfy.samplers.KSampler(
                        model=model, # Use the current model object
                        steps=steps,
                        device=device,
                        sampler=sampler_name,
                        scheduler=scheduler,
                        denoise=1.0,
                        model_options=model.model_options
                    )
                except Exception as e:
                     print(f"[HolafBenchmarkRunner] Error initializing KSampler for {sampler_name}/{scheduler} with model '{ckpt_name}': {e}")
                     print(f"[HolafBenchmarkRunner] Skipping resolution {res}x{res} for this model.")
                     error_row = [
                         f"{res}x{res}", steps, sampler_name, scheduler, "Init Error", "Error",
                         ckpt_name, model_family, system_info_dict["cpu"],
                         system_info_dict["ram_gb"], system_info_dict["gpu"], system_info_dict["gpu_mem_gb"], system_info_dict["os"]
                     ]
                     results_data.append(error_row)
                     continue

                # --- Run the sampling process and time it ---
                comfy.model_management.throw_exception_if_processing_interrupted()
                start_time = time.perf_counter()

                try:
                    seed = 0
                    cfg = 1.0
                    noise = comfy.sample.prepare_noise(latent_image, seed)
                    disable_pbar = True

                    _ = sampler.sample(
                        noise=noise,
                        positive=positive_cond,
                        negative=negative_cond,
                        cfg=cfg,
                        latent_image=latent_image,
                        start_step=0,
                        last_step=steps,
                        force_full_denoise=False,
                        denoise_mask=None,
                        sigmas=None,
                        callback=None,
                        disable_pbar=disable_pbar,
                        seed=seed
                    )

                except Exception as e:
                    end_time = time.perf_counter()
                    duration = end_time - start_time
                    print(f"[HolafBenchmarkRunner] Error during sampling for {res}x{res} with model '{ckpt_name}': {e}")
                    error_row = [
                        f"{res}x{res}", steps, sampler_name, scheduler, f"Sample Error ({duration:.3f}s)", "Error",
                        ckpt_name, model_family, system_info_dict["cpu"],
                        system_info_dict["ram_gb"], system_info_dict["gpu"], system_info_dict["gpu_mem_gb"], system_info_dict["os"]
                    ]
                    results_data.append(error_row)
                    continue # Skip to next resolution for this model

                end_time = time.perf_counter()
                # --- Calculation ---
                duration = end_time - start_time
                pixels = width * height
                pixels_per_second = pixels / duration if duration > 0 else 0

                print(f"[HolafBenchmarkRunner] Resolution {width}x{height} took {duration:.3f} seconds ({pixels_per_second:.2f} Pixels/s) for '{ckpt_name}'")
                # Append results row including system/model info
                results_row = [
                    f"{res}x{res}", steps, sampler_name, scheduler, f"{duration:.3f}", f"{pixels_per_second:.2f}",
                    ckpt_name, model_family, system_info_dict["cpu"],
                    system_info_dict["ram_gb"], system_info_dict["gpu"], system_info_dict["gpu_mem_gb"], system_info_dict["os"]
                ]
                results_data.append(results_row)

                # Optional small sleep?
                # time.sleep(0.05)

            model_end_time = time.perf_counter()
            print(f"[HolafBenchmarkRunner] === Benchmark for Model {model_index+1}: {ckpt_name} finished in {model_end_time - model_start_time:.3f} seconds ===")
            # --- End loop for resolutions ---
        # --- End loop for models ---

        overall_end_time = time.perf_counter()
        print(f"\n[HolafBenchmarkRunner] All benchmarks finished in {overall_end_time - overall_start_time:.3f} seconds.")

        # --- Format results as CSV string ---
        output_string = io.StringIO()
        writer = csv.writer(output_string)
        writer.writerows(results_data)
        report_text = output_string.getvalue()
        output_string.close()

        # Return the report string
        return (report_text,)

    def _get_system_info_only(self):
        """Collects only system information."""
        info = {
            "cpu": "N/A",
            "ram_gb": "N/A",
            "gpu": "N/A",
            "gpu_mem_gb": "N/A",
            "os": "N/A",
        }
        # --- System Info ---
        try:
            info["os"] = f"{platform.system()} {platform.release()}"
        except Exception as e:
            print(f"[HolafBenchmarkRunner] Warning: Error getting OS info: {e}")

        try:
            cpu_name = platform.processor() if hasattr(platform, 'processor') and platform.processor() else platform.machine()
            cpu_cores = psutil.cpu_count(logical=True) if psutil_available else '?'
            info["cpu"] = f"{cpu_name} ({cpu_cores} cores)"
        except Exception as e:
            print(f"[HolafBenchmarkRunner] Warning: Error getting CPU info: {e}")

        try:
            if psutil_available:
                mem = psutil.virtual_memory()
                info["ram_gb"] = self._bytes_to_gb(mem.total)
            else:
                info["ram_gb"] = "N/A (psutil missing)"
        except Exception as e:
            print(f"[HolafBenchmarkRunner] Warning: Error getting RAM info: {e}")

        try:
            if torch.cuda.is_available():
                gpu_id = torch.cuda.current_device()
                info["gpu"] = torch.cuda.get_device_name(gpu_id)
                props = torch.cuda.get_device_properties(gpu_id)
                info["gpu_mem_gb"] = self._bytes_to_gb(props.total_memory)
            else:
                info["gpu"] = "No CUDA GPU detected"
                info["gpu_mem_gb"] = 0.0
        except Exception as e:
            print(f"[HolafBenchmarkRunner] Warning: Error getting GPU info: {e}")
            info["gpu"] = "Error detecting GPU"
            info["gpu_mem_gb"] = "Error"

        print(f"[HolafBenchmarkRunner] System Info: OS={info['os']}, CPU={info['cpu']}, RAM={info['ram_gb']}GB, GPU={info['gpu']} ({info['gpu_mem_gb']}GB)")
        return info


# Node class mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "HolafBenchmarkRunner": HolafBenchmarkRunner
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafBenchmarkRunner": "Benchmark Runner (Holaf)" # Keep display name consistent
}
