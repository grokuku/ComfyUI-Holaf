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

# -----------------------------------------------------------------------------------
# FUSION LOGIQUE : Ce fichier est une fusion de HolafTiledKSampler original
# et des techniques avancées de ComfyUI-TiledDiffusion.
# Il conserve la structure d'un KSampler "tout-en-un" tout en remplaçant
# la logique de tiling basique par les algorithmes de Mixture of Diffusers,
# MultiDiffusion, et SpotDiffusion.
# -----------------------------------------------------------------------------------

import torch
import math
import numpy as np
import comfy.samplers
import comfy.utils
import comfy.model_management
from comfy.model_patcher import ModelPatcher

# --- IMPORTS ET LOGIQUE DE ComfyUI-TiledDiffusion ---
from typing import List, Union, Tuple, Callable
from enum import Enum
from numpy import pi, exp, sqrt

# Création d'un objet simple pour simuler la structure utilisée par TiledDiffusion
class TiledDiffusionDevices:
    def __init__(self):
        self.device = comfy.model_management.get_torch_device()
        self.cpu = torch.device('cpu')

devices = TiledDiffusionDevices()

def ceildiv(big, small):
    return -(big // -small)

class BBox:
    def __init__(self, x:int, y:int, w:int, h:int):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.box = [x, y, x + w, y + h]
        self.slicer = slice(None), slice(None), slice(y, y + h), slice(x, x + w)

    def __getitem__(self, idx:int) -> int:
        return self.box[idx]

def repeat_to_batch_size(tensor, batch_size, dim=0):
    if tensor.shape[dim] == 1 and dim == 0:
        return tensor.expand([batch_size] + [-1] * (len(tensor.shape) - 1))
    if tensor.shape[dim] > batch_size:
        return tensor.narrow(dim, 0, batch_size)
    elif tensor.shape[dim] < batch_size:
        repeats = [1] * dim + [ceildiv(batch_size, tensor.shape[dim])] + [1] * (len(tensor.shape) - 1 - dim)
        return tensor.repeat(repeats).narrow(dim, 0, batch_size)
    return tensor

def split_bboxes(w:int, h:int, tile_w:int, tile_h:int, overlap:int, init_weight:Union[torch.Tensor, float]=1.0) -> Tuple[List[BBox], torch.Tensor]:
    cols = ceildiv((w - overlap), (tile_w - overlap)) if (tile_w - overlap) > 0 else 1
    rows = ceildiv((h - overlap), (tile_h - overlap)) if (tile_h - overlap) > 0 else 1
    dx = (w - tile_w) / (cols - 1) if cols > 1 else 0
    dy = (h - tile_h) / (rows - 1) if rows > 1 else 0

    bbox_list: List[BBox] = []
    weight = torch.zeros((1, 1, h, w), device=devices.device, dtype=torch.float32)
    for row in range(rows):
        y = min(int(row * dy), h - tile_h) if rows > 1 else 0
        for col in range(cols):
            x = min(int(col * dx), w - tile_w) if cols > 1 else 0
            bbox = BBox(x, y, tile_w, tile_h)
            bbox_list.append(bbox)
            weight[bbox.slicer] += init_weight
    return bbox_list, weight

def gaussian_weights(tile_w:int, tile_h:int) -> torch.Tensor:
    f = lambda x, midpoint, var=0.01: exp(-(x - midpoint) * (x - midpoint) / (tile_w * tile_w) / (2 * var)) / sqrt(2 * pi * var)
    x_probs = [f(x, (tile_w - 1) / 2) for x in range(tile_w)]
    y_probs = [f(y, tile_h / 2) for y in range(tile_h)]
    w = np.outer(y_probs, x_probs)
    return torch.from_numpy(w).to(devices.device, dtype=torch.float32)

def find_nearest_in_list(a, b_list):
    diffs = [(a - b).abs() for b in b_list]
    return diffs.index(min(diffs))

class AbstractDiffusion:
    def __init__(self):
        self.w, self.h = 0, 0
        self.tile_width, self.tile_height, self.tile_overlap = 0, 0, 0
        self.x_buffer, self.weights = None, None
        self.batched_bboxes: List[List[BBox]] = []
        self.compression = 8 # Default
        self.sigmas = None

    def init_grid_bbox(self, tile_w:int, tile_h:int, overlap:int):
        self.weights = torch.zeros((1, 1, self.h, self.w), device=devices.device, dtype=torch.float32)
        self.tile_w, self.tile_h = min(tile_w, self.w), min(tile_h, self.h)
        overlap = max(0, min(overlap, min(self.tile_w, self.tile_h) - 4))
        
        bboxes, weights = split_bboxes(self.w, self.h, self.tile_w, self.tile_h, overlap, self.get_tile_weights())
        self.weights += weights
        self.batched_bboxes = [bboxes] # We force batch size of 1 for simplicity here

    def get_tile_weights(self) -> Union[torch.Tensor, float]: return 1.0 # For MultiDiffusion
    def reset_buffer(self, x_in:torch.Tensor):
        if self.x_buffer is None or self.x_buffer.shape != x_in.shape:
            self.x_buffer = torch.zeros_like(x_in)
        else:
            self.x_buffer.zero_()

class MultiDiffusion(AbstractDiffusion):
    @torch.inference_mode()
    def __call__(self, model_function, args):
        x_in, t_in, c_in = args["input"], args["timestep"], args["c"]
        N, C, H, W = x_in.shape
        if self.weights is None or self.h != H or self.w != W:
            self.h, self.w = H, W
            self.init_grid_bbox(self.tile_width, self.tile_height, self.tile_overlap)
        
        self.reset_buffer(x_in)
        
        for batch_id, bboxes in enumerate(self.batched_bboxes):
            x_tiles = torch.cat([x_in[bbox.slicer] for bbox in bboxes], dim=0)
            t_tiles = repeat_to_batch_size(t_in, x_tiles.shape[0])

            # --- BLOC CORRIGÉ ---
            c_tiles = {}
            for k, v in c_in.items():
                if isinstance(v, torch.Tensor):
                    c_tiles[k] = repeat_to_batch_size(v, x_tiles.shape[0])
                else:
                    c_tiles[k] = v
            
            x_tile_out = model_function(x_tiles, t_tiles, **c_tiles)

            for i, bbox in enumerate(bboxes):
                self.x_buffer[bbox.slicer] += x_tile_out[i*N:(i+1)*N]
        
        return torch.where(self.weights > 1, self.x_buffer / self.weights, self.x_buffer)

class MixtureOfDiffusers(MultiDiffusion):
    def __init__(self):
        super().__init__()
        self.tile_weights = None
        self.rescale_factor = None
    
    def get_tile_weights(self) -> torch.Tensor:
        self.tile_weights = gaussian_weights(self.tile_w, self.tile_h)
        return self.tile_weights

    @torch.inference_mode()
    def __call__(self, model_function, args):
        x_in, t_in, c_in = args["input"], args["timestep"], args["c"]
        N, C, H, W = x_in.shape
        if self.weights is None or self.h != H or self.w != W:
            self.h, self.w = H, W
            self.init_grid_bbox(self.tile_width, self.tile_height, self.tile_overlap)
            self.rescale_factor = 1.0 / self.weights
        
        self.reset_buffer(x_in)
        
        for batch_id, bboxes in enumerate(self.batched_bboxes):
            x_tiles = torch.cat([x_in[bbox.slicer] for bbox in bboxes], dim=0)
            t_tiles = repeat_to_batch_size(t_in, x_tiles.shape[0])

            # --- BLOC CORRIGÉ ---
            c_tiles = {}
            for k, v in c_in.items():
                if isinstance(v, torch.Tensor):
                    c_tiles[k] = repeat_to_batch_size(v, x_tiles.shape[0])
                else:
                    c_tiles[k] = v

            x_tile_out = model_function(x_tiles, t_tiles, **c_tiles)
            
            for i, bbox in enumerate(bboxes):
                w = self.tile_weights * self.rescale_factor[bbox.slicer]
                self.x_buffer[bbox.slicer] += x_tile_out[i*N:(i+1)*N] * w

        return self.x_buffer

class SpotDiffusion(MultiDiffusion):
    def __init__(self):
        super().__init__()
        self.uniform_distribution = None
        self.seed = 0

    @torch.inference_mode()
    def __call__(self, model_function, args):
        x_in, t_in, c_in = args["input"], args["timestep"], args["c"]
        N, C, H, W = x_in.shape
        if self.weights is None or self.h != H or self.w != W:
            self.h, self.w = H, W
            self.init_grid_bbox(self.tile_width, self.tile_height, self.tile_overlap)
        
        self.reset_buffer(x_in)

        if self.uniform_distribution is None:
            shift_height = torch.randint(0, self.tile_height, (len(self.sigmas)-1,), generator=torch.Generator(device='cpu').manual_seed(self.seed), device='cpu')
            shift_width = torch.randint(0, self.tile_width, (len(self.sigmas)-1,), generator=torch.Generator(device='cpu').manual_seed(self.seed+1), device='cpu')
            self.uniform_distribution = (shift_height, shift_width)
        
        ts_in = t_in
        cur_i = find_nearest_in_list(ts_in, self.sigmas)

        sh_h = 0
        sh_w = 0
        if cur_i < len(self.uniform_distribution):
            sh_h = self.uniform_distribution[cur_i].item()
            sh_w = self.uniform_distribution[cur_i].item()
        
        if self.tile_height >= H: sh_h = 0
        if self.tile_width >= W: sh_w = 0
        
        if (sh_h, sh_w) != (0,0):
            x_in = torch.roll(x_in, shifts=(sh_h, sh_w), dims=(-2,-1))
        
        for batch_id, bboxes in enumerate(self.batched_bboxes):
            x_tiles = torch.cat([x_in[bbox.slicer] for bbox in bboxes], dim=0)
            t_tiles = repeat_to_batch_size(t_in, x_tiles.shape[0])

            # --- BLOC CORRIGÉ ---
            c_tiles = {}
            for k, v in c_in.items():
                if isinstance(v, torch.Tensor):
                    c_tiles[k] = repeat_to_batch_size(v, x_tiles.shape[0])
                else:
                    c_tiles[k] = v

            x_tile_out = model_function(x_tiles, t_tiles, **c_tiles)

            for i, bbox in enumerate(bboxes):
                self.x_buffer[bbox.slicer] += x_tile_out[i*N:(i+1)*N]
        
        if (sh_h, sh_w) != (0,0):
            self.x_buffer = torch.roll(self.x_buffer, shifts=(-sh_h, -sh_w), dims=(-2,-1))
            
        return torch.where(self.weights > 1, self.x_buffer / self.weights, self.x_buffer)


# --- CLASSE DU NOEUD PRINCIPAL ---

class HolafTiledDiffusionKSampler:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": ("MODEL",), "positive": ("CONDITIONING",), "negative": ("CONDITIONING",), "vae": ("VAE",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1, "round": 0.01}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "denoise": ("FLOAT", {"default": 1.00, "min": 0.0, "max": 1.0, "step": 0.01}),
                
                "method": (["Mixture of Diffusers", "MultiDiffusion", "SpotDiffusion"], {
                    "default": "Mixture of Diffusers"
                }),
                "max_tile_size": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "overlap_size": ("INT", {"default": 128, "min": 0, "max": 8192, "step": 8}),

                "input_type": (["latent", "image"], {"default": "latent"}),
                "clean_vram": ("BOOLEAN", {"default": True}),
            },
            "optional": { "latent_image": ("LATENT",), "image": ("IMAGE",) }
        }

    RETURN_TYPES = ("MODEL", "CONDITIONING", "CONDITIONING", "VAE", "LATENT", "IMAGE")
    RETURN_NAMES = ("model", "positive", "negative", "vae", "latent", "image")
    FUNCTION = "sample_advanced_tiled"
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
        
        return int(final_tile_w), int(final_tile_h), int(overlap_size)

    def sample_advanced_tiled(self, model: ModelPatcher, positive, negative, vae,
                             seed, steps, cfg, sampler_name, scheduler, denoise,
                             method, max_tile_size, overlap_size,
                             input_type, clean_vram,
                             latent_image=None, image=None):

        print("HolafTiledDiffusionKSampler: Initializing advanced tiled sampling.")

        if clean_vram:
            print("  -> Cleaning VRAM...")
            comfy.model_management.soft_empty_cache()

        if input_type == "latent":
            if latent_image is None: raise ValueError("Input type is 'latent', but no latent_image provided.")
            latent = latent_image
        elif input_type == "image":
            if image is None: raise ValueError("Input type is 'image', but no image provided.")
            latent = {"samples": vae.encode(image[:,:,:,:3])}
        else:
            raise ValueError(f"Unknown input_type: {input_type}")
            
        latent_samples = latent["samples"]
        
        height_pixel = latent_samples.shape[2] * 8
        width_pixel = latent_samples.shape[3] * 8
        
        final_tile_w_px, final_tile_h_px, final_overlap_px = self.calculate_tile_params(
            width_pixel, height_pixel, max_tile_size, overlap_size)
        
        print(f"  -> Image dimensions: {width_pixel}x{height_pixel} pixels.")
        print(f"  -> Calculated tile dimensions: {final_tile_w_px}x{final_tile_h_px} with {final_overlap_px} overlap.")

        if method == "Mixture of Diffusers":
            impl = MixtureOfDiffusers()
        elif method == "MultiDiffusion":
            impl = MultiDiffusion()
        elif method == "SpotDiffusion":
            impl = SpotDiffusion()
            impl.seed = seed
            sigmas = comfy.samplers.calculate_sigmas_scheduler(model.model, scheduler, steps)
            impl.sigmas = sigmas.to(devices.device)
        else:
            raise ValueError(f"Unknown Tiling Method: {method}")

        print(f"  -> Using method: {method}")

        impl.tile_width = final_tile_w_px // 8
        impl.tile_height = final_tile_h_px // 8
        impl.tile_overlap = final_overlap_px // 8
        impl.compression = 8

        model_copy = model.clone()
        model_copy.set_model_unet_function_wrapper(impl)
        print("  -> Model patched temporarily with the tiling wrapper.")

        print("  -> Starting sampling process...")
        
        pbar = comfy.utils.ProgressBar(steps)
        def callback(step, x0, x, total_steps):
            pbar.update_absolute(step + 1, total_steps)

        device = model.load_device
        latent_samples = latent_samples.to(device)
        noise = comfy.sample.prepare_noise(latent_samples, seed, None).to(device)

        disable_noise = denoise == 0.0
            
        sampled_latent_samples = comfy.sample.sample(model_copy, noise, steps, cfg, sampler_name, scheduler, 
                                                     positive, negative, latent_samples, denoise=denoise, 
                                                     disable_noise=disable_noise, callback=callback, seed=seed)
        
        final_latent = {"samples": sampled_latent_samples.to(comfy.model_management.intermediate_device())}
        print("  -> Sampling finished.")

        print("  -> Decoding final latent to image...")
        image_out = vae.decode(final_latent["samples"])
        print("HolafTiledDiffusionKSampler: Process finished successfully.")

        return (model, positive, negative, vae, final_latent, image_out)

# --- ENREGISTREMENT DU NOEUD DANS COMFYUI ---
NODE_CLASS_MAPPINGS = {
    "HolafTiledDiffusionKSampler": HolafTiledDiffusionKSampler
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafTiledDiffusionKSampler": "Tiled Diffusion KSampler (Holaf)"
}