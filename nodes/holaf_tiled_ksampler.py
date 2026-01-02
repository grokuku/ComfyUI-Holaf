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

import torch
import math
import copy
import comfy.samplers
import comfy.utils
import comfy.model_management
from comfy.model_patcher import ModelPatcher

def prepare_cond_for_tile(original_cond_list, device):
    if not isinstance(original_cond_list, list): return []
    cond_list_copy = copy.deepcopy(original_cond_list)
    for i, item in enumerate(cond_list_copy):
        if isinstance(item, (list, tuple)) and len(item) >= 1 and torch.is_tensor(item[0]):
            if item[0].device != device: cond_list_copy[i][0] = item[0].to(device)
            if len(item) == 1: cond_list_copy[i].append({})
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
                "max_tile_size": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "overlap_size": ("INT", {"default": 128, "min": 0, "max": 8192, "step": 8}),
                "vae_decode": ("BOOLEAN", {"default": True}),
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
        overlap_size = min(overlap_size, max_tile_size - 8) if max_tile_size > 8 else 0
        tile_w_init = min(pixel_w, max_tile_size)
        tile_h_init = min(pixel_h, max_tile_size)
        step_w = tile_w_init - overlap_size
        step_h = tile_h_init - overlap_size
        x_slices = 1 if tile_w_init >= pixel_w or step_w <= 0 else 1 + math.ceil((pixel_w - tile_w_init) / step_w)
        y_slices = 1 if tile_h_init >= pixel_h or step_h <= 0 else 1 + math.ceil((pixel_h - tile_h_init) / step_h)
        final_tile_w = pixel_w if x_slices == 1 else math.ceil((pixel_w + (x_slices - 1) * overlap_size) / float(x_slices))
        final_tile_h = pixel_h if y_slices == 1 else math.ceil((pixel_h + (y_slices - 1) * overlap_size) / float(y_slices))
        final_tile_w = math.ceil(final_tile_w / 8.0) * 8
        final_tile_h = math.ceil(final_tile_h / 8.0) * 8
        overlap_size = math.ceil(overlap_size / 8.0) * 8
        step_w_final = final_tile_w - overlap_size
        step_h_final = final_tile_h - overlap_size
        x_slices = 1 if final_tile_w >= pixel_w or step_w_final <= 0 else 1 + math.ceil((pixel_w - final_tile_w) / step_w_final)
        y_slices = 1 if final_tile_h >= pixel_h or step_h_final <= 0 else 1 + math.ceil((pixel_h - final_tile_h) / step_h_final)
        return int(x_slices), int(y_slices), int(final_tile_w), int(final_tile_h), int(overlap_size)

    def sample_tiled(self, model: ModelPatcher, positive, negative, vae,
                     seed, steps, cfg, sampler_name, scheduler, denoise,
                     input_type, max_tile_size, overlap_size, vae_decode, clean_vram,
                     latent_image=None, image=None):
        
        if clean_vram: comfy.model_management.soft_empty_cache()
        
        # --- INPUT PREPARATION ---
        if input_type == "latent":
            if latent_image is None: raise ValueError("Input type is 'latent', but no latent_image provided.")
            latent = latent_image
        elif input_type == "image":
            if image is None: raise ValueError("Input type is 'image', but no image provided.")
            latent = {"samples": vae.encode(image[:,:,:,:3])}
        else: raise ValueError(f"Unknown input_type: {input_type}")
        
        if "samples" not in latent or not torch.is_tensor(latent["samples"]): 
            raise TypeError("Latent input is not a valid 'samples' tensor.")
        
        latent_samples = latent["samples"]
        device = model.load_device
        latent_samples = latent_samples.to(device)
        noise = comfy.sample.prepare_noise(latent_samples, seed, None).to(device)
        model_copy = model.clone()

        height_latent, width_latent = latent_samples.shape[-2], latent_samples.shape[-1]
        height_pixel, width_pixel = height_latent * 8, width_latent * 8
        
        x_slices, y_slices, tile_w_pixel, tile_h_pixel, overlap_pixel = self.calculate_tile_params(
            width_pixel, height_pixel, max_tile_size, overlap_size)
        
        tile_w_latent, tile_h_latent, overlap_latent = tile_w_pixel // 8, tile_h_pixel // 8, overlap_pixel // 8
        
        # --- 1. TILED SAMPLING PASS ---
        output_latent = torch.zeros_like(latent_samples)
        blend_mask = torch.zeros_like(latent_samples)
        
        # Create latent feather mask
        # Explicit shape [1, 1, 1, Width] to be compatible with [B, C, H, W] or [B, C, F, H, W]
        safe_overlap_x = min(overlap_latent, tile_w_latent // 2)
        safe_overlap_y = min(overlap_latent, tile_h_latent // 2)
        feather_mask_x = torch.ones((1, 1, 1, tile_w_latent), device=device)
        feather_mask_y = torch.ones((1, 1, tile_h_latent, 1), device=device)

        if safe_overlap_x > 0:
            for i in range(safe_overlap_x):
                weight = (i + 1) / float(safe_overlap_x + 1)
                feather_mask_x[:, :, :, i] = weight
                feather_mask_x[:, :, :, -(i + 1)] = weight
        if safe_overlap_y > 0:
            for i in range(safe_overlap_y):
                weight = (i + 1) / float(safe_overlap_y + 1)
                feather_mask_y[:, :, i, :] = weight
                feather_mask_y[:, :, -(i + 1), :] = weight
        
        tile_feather_mask_latent = feather_mask_y * feather_mask_x
        
        pbar = comfy.utils.ProgressBar(x_slices * y_slices)
        step_x_latent, step_y_latent = tile_w_latent - overlap_latent, tile_h_latent - overlap_latent
        
        print(f"HolafTiledKSampler: Sampling {x_slices * y_slices} tiles...")
        for y in range(y_slices):
            for x in range(x_slices):
                y_start, x_start = y * step_y_latent, x * step_x_latent
                if y_start + tile_h_latent > height_latent: y_start = height_latent - tile_h_latent
                if x_start + tile_w_latent > width_latent: x_start = width_latent - tile_w_latent
                y_end, x_end = y_start + tile_h_latent, x_start + tile_w_latent
                
                tile_latent = latent_samples[..., y_start:y_end, x_start:x_end]
                tile_noise = noise[..., y_start:y_end, x_start:x_end]
                
                tile_positive, tile_negative = prepare_cond_for_tile(positive, device), prepare_cond_for_tile(negative, device)
                sampled_output = comfy.sample.sample(model_copy, tile_noise, steps, cfg, sampler_name, scheduler, 
                                                    tile_positive, tile_negative, tile_latent, denoise=denoise, 
                                                    disable_noise=False, callback=None, disable_pbar=True, seed=seed)
                sampled_tile = sampled_output if torch.is_tensor(sampled_output) else sampled_output["samples"]
                
                output_latent[..., y_start:y_end, x_start:x_end] += sampled_tile.to(device) * tile_feather_mask_latent
                blend_mask[..., y_start:y_end, x_start:x_end] += tile_feather_mask_latent
                pbar.update(1)

        blend_mask = torch.clamp(blend_mask, min=1e-6)
        final_latent_samples = (output_latent / blend_mask).to(comfy.model_management.intermediate_device())
        final_latent = {"samples": final_latent_samples}
        
        # Detect if we are dealing with 5D latents (e.g. video)
        is_video = (final_latent_samples.ndim == 5)
        
        # --- 2. TILED VAE PASS (OR DUMMY) ---
        if vae_decode:
            if clean_vram: comfy.model_management.soft_empty_cache()
            print(f"HolafTiledKSampler: Decoding {x_slices * y_slices} tiles via VAE...")
            
            vae_device = comfy.model_management.vae_device()
            batch_size = final_latent_samples.shape[0]
            
            # Initialize output buffers
            if is_video:
                num_frames = final_latent_samples.shape[2]
                out_shape = (batch_size, num_frames, height_pixel, width_pixel, 3)
            else:
                out_shape = (batch_size, height_pixel, width_pixel, 3)
                
            image_out = torch.zeros(out_shape, device=device)
            image_blend_mask = torch.zeros(out_shape, device=device)
            
            # Create pixel feather mask for [B, H, W, C]
            # Explicit shape [1, 1, Width, 1] for X and [1, Height, 1, 1] for Y
            p_safe_overlap_x = min(overlap_pixel, tile_w_pixel // 2)
            p_safe_overlap_y = min(overlap_pixel, tile_h_pixel // 2)
            p_feather_x = torch.ones((1, 1, tile_w_pixel, 1), device=device)
            p_feather_y = torch.ones((1, tile_h_pixel, 1, 1), device=device)

            if p_safe_overlap_x > 0:
                for i in range(p_safe_overlap_x):
                    weight = (i + 1) / float(p_safe_overlap_x + 1)
                    p_feather_x[:, :, i, :] = weight
                    p_feather_x[:, :, -(i + 1), :] = weight
            if p_safe_overlap_y > 0:
                for i in range(p_safe_overlap_y):
                    weight = (i + 1) / float(p_safe_overlap_y + 1)
                    p_feather_y[:, i, :, :] = weight
                    p_feather_y[:, -(i + 1), :, :] = weight
            
            tile_feather_mask_pixel = p_feather_y * p_feather_x
            
            pbar_vae = comfy.utils.ProgressBar(x_slices * y_slices)
            for y in range(y_slices):
                for x in range(x_slices):
                    # Coordinates in latent
                    ly_start, lx_start = y * step_y_latent, x * step_x_latent
                    if ly_start + tile_h_latent > height_latent: ly_start = height_latent - tile_h_latent
                    if lx_start + tile_w_latent > width_latent: lx_start = width_latent - tile_w_latent
                    ly_end, lx_end = ly_start + tile_h_latent, lx_start + tile_w_latent
                    
                    # Coordinates in pixels
                    py_start, px_start = ly_start * 8, lx_start * 8
                    py_end, px_end = ly_end * 8, lx_end * 8
                    
                    # Slice latent and move to VAE device
                    tile_latent_subset = final_latent_samples[..., ly_start:ly_end, lx_start:lx_end].to(vae_device)
                    decoded_tile = vae.decode(tile_latent_subset).to(device)
                    
                    # Add to accumulation buffers
                    image_out[..., py_start:py_end, px_start:px_end, :] += decoded_tile * tile_feather_mask_pixel
                    image_blend_mask[..., py_start:py_end, px_start:px_end, :] += tile_feather_mask_pixel
                    pbar_vae.update(1)
            
            image_blend_mask = torch.clamp(image_blend_mask, min=1e-6)
            image_out = (image_out / image_blend_mask).to(comfy.model_management.intermediate_device())
        else:
            print("HolafTiledKSampler: VAE Decode skipped (outputting dummy image).")
            if is_video:
                num_frames = final_latent_samples.shape[2]
                image_out = torch.zeros((batch_size, num_frames, 8, 8, 3))
            else:
                image_out = torch.zeros((batch_size, 8, 8, 3))

        final_latent["samples"] = final_latent["samples"].cpu()
        return (model, positive, negative, vae, final_latent, image_out)