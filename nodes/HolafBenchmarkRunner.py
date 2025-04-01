import torch
import time
import csv
import os
import folder_paths
import comfy.samplers
import comfy.sample
import comfy.model_management
import nodes as comfy_nodes # Import the nodes module to potentially reuse EmptyLatentImage logic

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
# 5. Saves all results (Resolution, Steps, Sampler, Scheduler, Time (s), Pixels/s)
#    to a CSV file in the ComfyUI `output` directory.
# 6. Returns the path to the generated CSV file.
#
# Inputs:
# - model (MODEL): The model to use for the benchmark (influences sampler behavior).
# - resolutions (STRING): Comma-separated list of resolutions and/or ranges.
#   Examples: "512, 1024", "512-1024:128", "512, 768-1024:128, 2048"
#   Range format: "start-end:step". Step is optional, defaults to 64 or similar if omitted? (Let's require step for now).
# - steps (INT): Number of sampling steps.
# - sampler_name (COMBO): The sampler to use.
# - scheduler (COMBO): The scheduler to use.
# - trigger (BOOLEAN): A toggle acting as a button to start the benchmark process on queue.
#
# Outputs:
# - report_text (STRING): The benchmark results formatted as a CSV string.
#
# Dependencies:
# - Requires standard Python libraries (time, csv, os).
# - Relies on ComfyUI's internal modules (torch, folder_paths, comfy.samplers, comfy.sample, comfy.model_management).
#
# ==================================================================================
import re # For parsing resolutions

class HolafBenchmarkRunner:
    def __init__(self):
        pass # No need for output_dir anymore

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": ("MODEL",),
                "resolutions": ("STRING", {"default": "512, 768-1024:128", "multiline": False}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS, ),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, ),
                # Using a custom widget name that hopefully triggers execution
                "trigger": ("BOOLEAN", {"default": False, "label_on": "RUN BENCHMARK", "label_off": "RUN BENCHMARK"}),
            },
            # No optional inputs anymore
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

    def run_benchmark(self, model, resolutions, steps, sampler_name, scheduler, trigger):
        # The 'trigger' parameter ensures this runs when queued after the button is pressed.

        parsed_resolutions = self.parse_resolutions(resolutions)
        if not parsed_resolutions:
            print("[HolafBenchmarkRunner] Error: No valid resolutions to test.")
            return ("",) # Return empty string on error

        results_data = []
        # Header for CSV data
        header = ["Resolution", "Steps", "Sampler", "Scheduler", "Time (s)", "Pixels/s"]
        results_data.append(header)

        # --- Prepare inputs for comfy.sample.sample ---
        # Use the provided model.
        # Still need minimal conditioning as samplers expect it.
        device = comfy.model_management.get_torch_device()
        batch_size = 1

        # Determine conditioning dimension from the model if possible, default otherwise
        cond_dim = 768 # Default SD1.5/SD2
        if hasattr(model, 'model') and hasattr(model.model, 'embedding_dim'): # Basic check
             try:
                 cond_dim = model.model.embedding_dim
                 print(f"[HolafBenchmarkRunner] Inferred cond_dim from model: {cond_dim}")
             except Exception:
                 print(f"[HolafBenchmarkRunner] Could not infer cond_dim, using default: {cond_dim}")

        # Minimal conditioning tensors
        # Using zeros might be sufficient for timing, but check if specific samplers fail.
        positive_cond = [[torch.zeros([batch_size, 77, cond_dim], device=device), {}]] # Simplified structure
        negative_cond = [[torch.zeros([batch_size, 77, cond_dim], device=device), {}]]

        print(f"[HolafBenchmarkRunner] Starting benchmark for {len(parsed_resolutions)} resolutions...")

        total_start_time = time.perf_counter()

        for i, res in enumerate(parsed_resolutions):
            width = res
            height = res
            # Ensure latent dimensions are valid (at least 1x1 after division by 8)
            latent_height = max(1, height // 8)
            latent_width = max(1, width // 8)
            latent_image = torch.zeros([batch_size, 4, latent_height, latent_width], device=device)
            # latent = {"samples": latent_image} # KSampler takes latent_image directly now

            print(f"[HolafBenchmarkRunner] ({i+1}/{len(parsed_resolutions)}) Testing resolution: {width}x{height}")

            # Initialize the KSampler *inside* the loop?
            # Or outside if model doesn't change? Let's keep it outside for efficiency.
            # Need to ensure KSampler instance is created correctly with the real model.
            try:
                # Create KSampler instance once before the loop if possible
                # However, some internal state might depend on latent size? Re-creating might be safer.
                 sampler = comfy.samplers.KSampler(
                    model=model, # Use the provided model object
                    steps=steps,
                    device=device,
                    sampler=sampler_name,
                    scheduler=scheduler,
                    denoise=1.0, # Denoise fully for measurement? Yes, for consistent timing.
                    model_options=model.model_options # Pass model options along
                )
            except Exception as e:
                 print(f"[HolafBenchmarkRunner] Error initializing KSampler for {sampler_name}/{scheduler} with provided model: {e}")
                 print(f"[HolafBenchmarkRunner] Skipping resolution {res}x{res}.")
                 # Use header names for clarity when adding error row
                 results_data.append([f"{res}x{res}", steps, sampler_name, scheduler, "Init Error", "Error"])
                 continue

            # --- Run the sampling process and time it ---
            # Ensure model is loaded if necessary (ComfyUI might handle this)
            # comfy.model_management.load_model_gpu(model) # Is this needed here? Probably handled by workflow execution.

            comfy.model_management.throw_exception_if_processing_interrupted()
            start_time = time.perf_counter()

            try:
                seed = 0 # Fixed seed for consistency
                cfg = 1.0 # Minimal CFG - adjust if needed for specific samplers, but keep low for pure speed test
                noise = comfy.sample.prepare_noise(latent_image, seed) # Generate noise based on latent shape
                disable_pbar = True # No progress bar

                # Call the sampler's sample method directly
                _ = sampler.sample(
                    noise=noise,
                    positive=positive_cond,
                    negative=negative_cond,
                    cfg=cfg,
                    latent_image=latent_image,
                    start_step=0,
                    last_step=steps,
                    force_full_denoise=False, # Standard behavior
                    denoise_mask=None,
                    sigmas=None, # Let KSampler handle sigmas based on scheduler/steps
                    callback=None,
                    disable_pbar=disable_pbar,
                    seed=seed
                )
                # We ignore the output latent samples (_)

            except Exception as e:
                end_time = time.perf_counter() # Stop timer even on error
                duration = end_time - start_time
                print(f"[HolafBenchmarkRunner] Error during sampling for {res}x{res}: {e}")
                results_data.append([f"{res}x{res}", steps, sampler_name, scheduler, f"Sample Error ({duration:.3f}s)", "Error"])
                # Record the error and continue
                continue # Skip to next resolution

            end_time = time.perf_counter()
            # --- Calculation ---
            duration = end_time - start_time
            pixels = width * height
            pixels_per_second = pixels / duration if duration > 0 else 0

            print(f"[HolafBenchmarkRunner] Resolution {width}x{height} took {duration:.3f} seconds ({pixels_per_second:.2f} Pixels/s)")
            results_data.append([f"{res}x{res}", steps, sampler_name, scheduler, f"{duration:.3f}", f"{pixels_per_second:.2f}"])

            # Optional small sleep? Probably not needed unless hitting weird resource limits.
            # time.sleep(0.05)

        total_end_time = time.perf_counter()
        total_duration = total_end_time - total_start_time
        print(f"[HolafBenchmarkRunner] Benchmark finished in {total_duration:.3f} seconds.")

        # --- Format results as CSV string ---
        output_string = io.StringIO()
        writer = csv.writer(output_string)
        writer.writerows(results_data)
        report_text = output_string.getvalue()
        output_string.close()

        # Return the report string
        return (report_text,)

# Node class mappings for ComfyUI
# Need to import io and csv at the top
import io
import csv

NODE_CLASS_MAPPINGS = {
    "HolafBenchmarkRunner": HolafBenchmarkRunner
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafBenchmarkRunner": "Benchmark Runner (Holaf)" # Keep display name consistent
}
