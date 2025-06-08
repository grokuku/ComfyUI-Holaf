import torch
import math
import numpy as np
import copy
import comfy.samplers
import comfy.utils
import comfy.model_management
from comfy.model_patcher import ModelPatcher

def prepare_cond_for_tile(original_cond_list, device):
    """
    Deep copies a conditioning list and moves its tensors to the specified device.
    This is vital for tiled sampling to ensure each tile's sampling process
    is isolated and uses a fresh copy of the conditioning data.
    """
    if not isinstance(original_cond_list, list):
        return []

    cond_list_copy = copy.deepcopy(original_cond_list)
    for i, item in enumerate(cond_list_copy):
        if isinstance(item, (list, tuple)) and len(item) >= 1 and torch.is_tensor(item[0]):
            if item[0].device != device:
                cond_list_copy[i][0] = item[0].to(device)
            if len(item) == 1:
                 cond_list_copy[i].append({})
        elif torch.is_tensor(item):
            tensor_on_device = item.to(device) if item.device != device else item
            cond_list_copy[i] = [tensor_on_device, {}]
    return cond_list_copy


class HolafTiledKSampler:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": ("MODEL",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "vae": ("VAE",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1, "round": 0.01}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "denoise": ("FLOAT", {"default": 1.00, "min": 0.0, "max": 1.0, "step": 0.01}),
                "input_type": (["latent", "image"], {"default": "latent"}),
                # The max dimension of a tile, should align with the model's native resolution (e.g., 1024 for SDXL).
                "max_tile_size": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                # Pixel overlap between adjacent tiles to ensure seamless blending.
                "overlap_size": ("INT", {"default": 128, "min": 0, "max": 8192, "step": 8}),
                "clean_vram": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                 "latent_image": ("LATENT",),
                 "image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("MODEL", "CONDITIONING", "CONDITIONING", "VAE", "LATENT", "IMAGE")
    RETURN_NAMES = ("model", "positive", "negative", "vae", "latent", "image")
    FUNCTION = "sample_tiled"
    CATEGORY = "Holaf"

    def calculate_tile_params(self, pixel_w, pixel_h, max_tile_size, overlap_size):
        """
        Calculates tile grid parameters. The key step here is ensuring all final
        dimensions (tile size, overlap) are divisible by 8, which is required for
        compatibility with the VAE's latent space (8x compression factor).
        """
        overlap_size = min(overlap_size, max_tile_size - 8) if max_tile_size > 8 else 0
        tile_w_init = min(pixel_w, max_tile_size)
        tile_h_init = min(pixel_h, max_tile_size)
        step_w = tile_w_init - overlap_size
        step_h = tile_h_init - overlap_size

        x_slices = 1 if tile_w_init >= pixel_w or step_w <= 0 else 1 + math.ceil((pixel_w - tile_w_init) / step_w)
        y_slices = 1 if tile_h_init >= pixel_h or step_h <= 0 else 1 + math.ceil((pixel_h - tile_h_init) / step_h)

        final_tile_w = pixel_w if x_slices == 1 else math.ceil((pixel_w + (x_slices - 1) * overlap_size) / float(x_slices))
        final_tile_h = pixel_h if y_slices == 1 else math.ceil((pixel_h + (y_slices - 1) * overlap_size) / float(y_slices))

        # Ensure final dimensions and overlap are divisible by 8 for latent space compatibility.
        final_tile_w = math.ceil(final_tile_w / 8.0) * 8
        final_tile_h = math.ceil(final_tile_h / 8.0) * 8
        overlap_size = math.ceil(overlap_size / 8.0) * 8

        # Recalculate slice counts based on the adjusted, rounded tile sizes.
        step_w_final = final_tile_w - overlap_size
        step_h_final = final_tile_h - overlap_size
        x_slices = 1 if final_tile_w >= pixel_w or step_w_final <= 0 else 1 + math.ceil((pixel_w - final_tile_w) / step_w_final)
        y_slices = 1 if final_tile_h >= pixel_h or step_h_final <= 0 else 1 + math.ceil((pixel_h - final_tile_h) / step_h_final)

        return int(x_slices), int(y_slices), int(final_tile_w), int(final_tile_h), int(overlap_size)

    def sample_tiled(self, model: ModelPatcher, positive, negative, vae,
                     seed, steps, cfg, sampler_name, scheduler, denoise,
                     input_type, max_tile_size, overlap_size, clean_vram,
                     latent_image=None, image=None):
        if clean_vram:
            comfy.model_management.soft_empty_cache()

        # --- Input Preparation ---
        if input_type == "latent":
            if latent_image is None: raise ValueError("Input type is 'latent', but no latent_image provided.")
            latent = latent_image
        elif input_type == "image":
            if image is None: raise ValueError("Input type is 'image', but no image provided.")
            encoded_output = vae.encode(image[:,:,:,:3])
            latent = {"samples": encoded_output} if torch.is_tensor(encoded_output) else encoded_output
        else: raise ValueError(f"Unknown input_type: {input_type}")

        if "samples" not in latent or not torch.is_tensor(latent["samples"]):
             raise TypeError("Latent input is not a dictionary with a valid 'samples' tensor.")

        latent_samples = latent["samples"]
        device = model.load_device
        latent_samples = latent_samples.to(device)
        noise = comfy.sample.prepare_noise(latent_samples, seed, None).to(device)
        model_copy = model.clone()

        # --- Tiling Calculation ---
        height_latent, width_latent = latent_samples.shape[2], latent_samples.shape[3]
        height_pixel, width_pixel = height_latent * 8, width_latent * 8
        x_slices, y_slices, tile_w_pixel, tile_h_pixel, overlap_pixel = self.calculate_tile_params(
            width_pixel, height_pixel, max_tile_size, overlap_size)
        tile_w_latent, tile_h_latent, overlap_latent = tile_w_pixel // 8, tile_h_pixel // 8, overlap_pixel // 8

        # --- Blending Mask Preparation ---
        # A feathering mask is used for smooth blending. It has a value of 1.0 in the
        # center and linearly fades to 0 at the edges of the overlap area.
        output_latent = torch.zeros_like(latent_samples)
        blend_mask = torch.zeros_like(latent_samples)
        feather_mask_x = torch.ones((1, 1, 1, tile_w_latent), device=device)
        feather_mask_y = torch.ones((1, 1, tile_h_latent, 1), device=device)

        if overlap_latent > 0:
            for i in range(overlap_latent):
                weight = (i + 1) / float(overlap_latent + 1)
                feather_mask_x[..., i] = weight
                feather_mask_x[..., -(i + 1)] = weight
                feather_mask_y[..., i, :] = weight
                feather_mask_y[..., -(i + 1), :] = weight
        tile_feather_mask = feather_mask_y * feather_mask_x

        # --- Tiling Loop ---
        pbar = comfy.utils.ProgressBar(x_slices * y_slices)
        step_x_latent = tile_w_latent - overlap_latent
        step_y_latent = tile_h_latent - overlap_latent

        for y in range(y_slices):
            for x in range(x_slices):
                # Calculate coordinates for the current tile, handling edge cases.
                y_start = y * step_y_latent
                x_start = x * step_x_latent
                if y_start + tile_h_latent > height_latent: y_start = height_latent - tile_h_latent
                if x_start + tile_w_latent > width_latent: x_start = width_latent - tile_w_latent
                y_end, x_end = y_start + tile_h_latent, x_start + tile_w_latent

                # Extract the portions of the latent and noise for this tile.
                tile_latent = latent_samples[:, :, y_start:y_end, x_start:x_end]
                tile_noise = noise[:, :, y_start:y_end, x_start:x_end]
                tile_positive = prepare_cond_for_tile(positive, device)
                tile_negative = prepare_cond_for_tile(negative, device)

                # Sample the individual tile.
                sampled_output = comfy.sample.sample(model_copy, tile_noise, steps, cfg, sampler_name, scheduler,
                                                     tile_positive, tile_negative, tile_latent,
                                                     denoise=denoise, disable_noise=False, callback=None,
                                                     disable_pbar=True, seed=seed)
                
                sampled_tile = sampled_output if torch.is_tensor(sampled_output) else sampled_output["samples"]
                
                # Add the weighted result to the main output. Also accumulate the weights in the blend_mask.
                output_latent[:, :, y_start:y_end, x_start:x_end] += sampled_tile.to(device) * tile_feather_mask
                blend_mask[:, :, y_start:y_end, x_start:x_end] += tile_feather_mask
                pbar.update(1)

        # --- Finalize and Decode ---
        # Average the blended tiles by dividing the accumulated output by the accumulated
        # blend mask. This normalizes the values in overlapping regions.
        blend_mask = torch.clamp(blend_mask, min=1e-6) # Avoid division by zero.
        final_latent_samples = (output_latent / blend_mask).to(comfy.model_management.intermediate_device())
        
        final_latent = {"samples": final_latent_samples}
        image_out = vae.decode(final_latent["samples"]).to(comfy.model_management.intermediate_device())
        final_latent["samples"] = final_latent["samples"].cpu()

        return (model, positive, negative, vae, final_latent, image_out)