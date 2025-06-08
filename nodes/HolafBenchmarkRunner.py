import torch
import time
import csv
import io
import re
import traceback
import platform
import folder_paths
import comfy.samplers
import comfy.sample
import comfy.model_management

# Attempt to import psutil for detailed system info; fail gracefully if not available.
try:
    import psutil
    psutil_available = True
except ImportError:
    psutil_available = False
    print("[HolafBenchmarkRunner] Warning: 'psutil' is not installed. CPU/RAM details will be limited. `pip install psutil`")

class HolafBenchmarkRunner:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "holaf_model_info_list": ("HOLAF_MODEL_INFO_LIST",),
                # A flexible string to define multiple resolutions.
                # Examples: "512, 1024", "512-1024:128"
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

    def parse_resolutions(self, res_string):
        """
        Parses a flexible string into a list of resolutions.
        Supports single numbers (512), comma-separated lists (512,1024),
        and ranges with steps (768-1024:128). It also validates that
        resolutions are positive and divisible by 8 for latent space compatibility.
        """
        final_res = set()
        for part in res_string.split(','):
            part = part.strip()
            if not part: continue
            range_match = re.match(r"(\d+)-(\d+):(\d+)", part)
            if range_match:
                start, end, step = map(int, range_match.groups())
                if start <= end and step > 0:
                    final_res.update(range(start, end + 1, step))
            elif part.isdigit():
                final_res.add(int(part))
        
        valid_res = {r for r in final_res if r > 0 and r % 8 == 0}
        return sorted(list(valid_res))

    def _get_system_info(self):
        """Collects system hardware information for the report header."""
        info = {"CPU": "N/A", "RAM (GB)": "N/A", "GPU": "N/A", "GPU Memory (GB)": "N/A", "OS": "N/A"}
        try:
            info["OS"] = f"{platform.system()} {platform.release()}"
            if psutil_available:
                info["CPU"] = f"{platform.processor() or platform.machine()} ({psutil.cpu_count(logical=True)} cores)"
                info["RAM (GB)"] = round(psutil.virtual_memory().total / (1024**3), 2)
            if torch.cuda.is_available():
                gpu_id = torch.cuda.current_device()
                info["GPU"] = torch.cuda.get_device_name(gpu_id)
                info["GPU Memory (GB)"] = round(torch.cuda.get_device_properties(gpu_id).total_memory / (1024**3), 2)
        except Exception: pass
        return info

    def run_benchmark(self, holaf_model_info_list, resolutions, steps, sampler_name, scheduler):
        if not isinstance(holaf_model_info_list, list) or not holaf_model_info_list:
            return ("",)

        parsed_resolutions = self.parse_resolutions(resolutions)
        if not parsed_resolutions: return ("",)

        system_info = self._get_system_info()
        results_data = []
        header = ["Resolution", "Steps", "Sampler", "Scheduler", "Time (s)", "Pixels/s", "Model Name", "Model Type"] + list(system_info.keys())
        results_data.append(header)

        device = comfy.model_management.get_torch_device()
        
        for model_info in holaf_model_info_list:
            model_object, model_name, model_type = model_info['model'], model_info['name'], model_info['type']
            print(f"\n--- Benchmarking: {model_name} (Type: {model_type}) ---")

            if model_type == 'FLUX':
                print(f"Warning: Benchmarking raw FLUX UNets is unsupported. Skipping '{model_name}'.")
                continue

            for res in parsed_resolutions:
                width, height = res, res
                latent_h, latent_w = height // 8, width // 8
                latent_image = torch.zeros([1, 4, latent_h, latent_w], device=device)
                print(f"  Testing {width}x{height}...")
                
                duration, pps = "Error", "Error"
                try:
                    # Create dummy conditioning appropriate for the model family (SD1.5 vs SDXL).
                    cond_dim = 2048 if "xl" in model_name.lower() else 768
                    cond_pooled = {"pooled_output": torch.zeros([1, 1280], device=device)} if "xl" in model_name.lower() else {}
                    positive = [[torch.zeros([1, 77, cond_dim], device=device), cond_pooled]]
                    negative = [[torch.zeros([1, 77, cond_dim], device=device), cond_pooled]]

                    sampler = comfy.samplers.KSampler(model_object, steps, device, sampler_name, scheduler)
                    noise = comfy.sample.prepare_noise(latent_image, 0)
                    
                    comfy.model_management.throw_exception_if_processing_interrupted()
                    start_time = time.perf_counter()
                    sampler.sample(noise, positive, negative, cfg=1.0, latent_image=latent_image, disable_pbar=True)
                    end_time = time.perf_counter()

                    duration = end_time - start_time
                    pps = (width * height) / duration if duration > 0 else 0
                except Exception as e:
                    print(f"  ERROR at {width}x{height}: {e}")
                    traceback.print_exc()

                row = [f"{width}x{height}", steps, sampler_name, scheduler,
                       f"{duration:.3f}" if isinstance(duration, float) else duration,
                       f"{pps:.2f}" if isinstance(pps, float) else pps,
                       model_name, model_type] + list(system_info.values())
                results_data.append(row)

        # Convert the results list into a single CSV-formatted string.
        output_io = io.StringIO()
        writer = csv.writer(output_io)
        writer.writerows(results_data)
        report_text = output_io.getvalue()
        output_io.close()
        
        return (report_text,)