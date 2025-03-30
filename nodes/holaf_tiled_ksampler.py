import torch
import math
import numpy as np
# from tqdm import tqdm # Removed unused import
import copy # Re-add copy for deepcopy

import comfy.samplers
import comfy.utils
import comfy.model_management
from comfy.model_patcher import ModelPatcher

# Tensor related imports might be needed later
# from comfy.ldm.modules.diffusionmodules.util import make_ddim_sampling_parameters, make_ddim_timesteps, noise_like

def prepare_cond_for_tile(original_cond_list, device):
    """
    Creates a deep copy of the conditioning list for a tile and moves tensors within the copy to the specified device.
    Returns the new list structure.
    """
    if not isinstance(original_cond_list, list):
        # print(f"Warning: Conditioning input is not a list, but type {type(original_cond_list)}. Returning empty list.")
        return [] # Return empty list if not a list

    cond_list_copy = copy.deepcopy(original_cond_list)
    for i, item in enumerate(cond_list_copy):
        if isinstance(item, (list, tuple)) and len(item) >= 1 and torch.is_tensor(item[0]):
            # Standard format: [tensor, {dict}] - move tensor in the copy
            if item[0].device != device:
                try:
                    cond_list_copy[i][0] = item[0].to(device)
                except Exception as e:
                    print(f"Error moving tensor to device {device}: {e}")
            # Ensure the dict exists if only tensor was present in original
            if len(item) == 1:
                 cond_list_copy[i].append({})
            elif not isinstance(item[1], dict): # Ensure second element is a dict if tensor exists
                 print(f"Warning: Conditioning item format issue. Expected dict as second element, got {type(item[1])}. Replacing with empty dict.")
                 cond_list_copy[i] = [cond_list_copy[i][0], {}]

        elif torch.is_tensor(item):
            # Handle cases where the list might just contain tensors - move tensor in the copy
            tensor_on_device = item
            if item.device != device:
                 try:
                     tensor_on_device = item.to(device)
                 except Exception as e:
                     print(f"Error moving tensor to device {device}: {e}")
            # Replace the tensor with the standard [tensor, {}] format in the copy
            cond_list_copy[i] = [tensor_on_device, {}]
        # Ignore other formats (already copied by deepcopy)

    return cond_list_copy


class HolafTiledKSampler:
    @classmethod
    def INPUT_TYPES(s):
        # Get available sampler and scheduler names from ComfyUI
        samplers = comfy.samplers.KSampler.SAMPLERS
        schedulers = comfy.samplers.KSampler.SCHEDULERS
        return {
            "required": {
                "model": ("MODEL",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "vae": ("VAE",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "control_after_generate": (["fixed", "increment", "decrement", "randomize"], {"default": "randomize"}), # Re-added
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1, "round": 0.01}),
                "sampler_name": (samplers,),
                "scheduler": (schedulers,),
                "denoise": ("FLOAT", {"default": 1.00, "min": 0.0, "max": 1.0, "step": 0.01}),
                "input_type": (["latent", "image"], {"default": "latent"}),
                "max_tile_size": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "overlap_size": ("INT", {"default": 128, "min": 0, "max": 8192, "step": 8}),
                # "batch_size": ("INT", {"default": 1, "min": 1, "max": 4096}), # Removed batch size as tiling implies batch=1
                # "use_sliced_conditioning": ("BOOLEAN", {"default": True}), # Removed this option
            },
            "optional": {
                 "latent_image": ("LATENT",), # Optional now, required if input_type is latent
                 "image": ("IMAGE",),       # Optional now, required if input_type is image
            }
        }

    RETURN_TYPES = ("MODEL", "CONDITIONING", "CONDITIONING", "VAE", "LATENT", "IMAGE")
    RETURN_NAMES = ("model", "positive", "negative", "vae", "latent", "image")
    FUNCTION = "sample_tiled"
    CATEGORY = "Holaf"

    def calculate_tile_params(self, pixel_w, pixel_h, max_tile_size, overlap_size):
        """
        Calculates tile parameters based on pixel dimensions.
        Adapted from HolafTileCalculator.
        Returns: x_slices, y_slices, tile_w_pixel, tile_h_pixel
        """
        # Clamp overlap to be less than max_tile_size
        overlap_size = min(overlap_size, max_tile_size - 8) if max_tile_size > 8 else 0

        tile_w = min(pixel_w, max_tile_size)
        tile_h = min(pixel_h, max_tile_size)

        step_w = tile_w - overlap_size
        step_h = tile_h - overlap_size

        x_slices = 1 if tile_w >= pixel_w or step_w <= 0 else 1 + math.ceil((pixel_w - tile_w) / step_w)
        y_slices = 1 if tile_h >= pixel_h or step_h <= 0 else 1 + math.ceil((pixel_h - tile_h) / step_h)

        # Calculate the precise tile size needed for a potentially better fit
        # D = (A + (N - 1) * C) / N
        final_tile_w = pixel_w if x_slices == 1 else math.ceil((pixel_w + (x_slices - 1) * overlap_size) / float(x_slices))
        final_tile_h = pixel_h if y_slices == 1 else math.ceil((pixel_h + (y_slices - 1) * overlap_size) / float(y_slices))

        # Ensure tile dimensions are divisible by 8 for latent conversion
        final_tile_w = math.ceil(final_tile_w / 8.0) * 8
        final_tile_h = math.ceil(final_tile_h / 8.0) * 8
        overlap_size = math.ceil(overlap_size / 8.0) * 8 # Also ensure overlap is divisible by 8

        # Recalculate slices based on adjusted tile sizes if necessary (though the ceil should handle it)
        step_w = final_tile_w - overlap_size
        step_h = final_tile_h - overlap_size
        x_slices = 1 if final_tile_w >= pixel_w or step_w <= 0 else 1 + math.ceil((pixel_w - final_tile_w) / step_w)
        y_slices = 1 if final_tile_h >= pixel_h or step_h <= 0 else 1 + math.ceil((pixel_h - final_tile_h) / step_h)

        return int(x_slices), int(y_slices), int(final_tile_w), int(final_tile_h), int(overlap_size)


    def sample_tiled(self, model: ModelPatcher, positive, negative, vae,
                     seed, control_after_generate, steps, cfg, sampler_name, scheduler, denoise,
                     input_type, max_tile_size, overlap_size, # Removed batch_size and use_sliced_conditioning
                     latent_image=None, image=None):

        # --- Input Validation ---
        if input_type == "latent":
            if latent_image is None:
                raise ValueError("Input type is 'latent', but no latent_image provided.")
            latent = latent_image
        elif input_type == "image":
            if image is None:
                raise ValueError("Input type is 'image', but no image provided.")
            if image is None:
                raise ValueError("Input type is 'image', but no image provided.")
            # Perform encoding
            if hasattr(vae, 'encode_pil_to_latent'):
                 encoded_output = vae.encode_pil_to_latent(image)
            else:
                 encoded_output = vae.encode(image[:,:,:,:3]) # Assuming image is BCHW, take RGB

            # Check if encode already returned a dict or just the tensor
            if isinstance(encoded_output, dict) and "samples" in encoded_output:
                latent = encoded_output # Use the dict directly
            elif torch.is_tensor(encoded_output):
                latent = {"samples": encoded_output} # Wrap tensor in dict
            else:
                raise TypeError(f"VAE encode returned unexpected type: {type(encoded_output)}")
        else:
            raise ValueError(f"Unknown input_type: {input_type}")

        if "samples" not in latent:
             raise TypeError("Latent input is not a dictionary with 'samples' key.")

        # Ensure the 'samples' value is actually a tensor before proceeding
        if not torch.is_tensor(latent["samples"]):
            raise TypeError(f"Latent['samples'] is not a tensor, but type: {type(latent['samples'])}")

        latent_samples = latent["samples"] # Now we are sure it's a tensor
        device = model.load_device # Get the target device from the model
        latent_samples = latent_samples.to(device) # Move the input latent to the correct device

        # Prepare noise on the correct device
        noise = comfy.sample.prepare_noise(latent_samples, seed, None).to(device) # Use batch_idx=None for now

        # Conditioning lists (positive, negative) will be deep-copied inside the loop

        # Clone the model ONCE before the loop to prevent potential modifications
        model_copy = model.clone()

        # --- Get Dimensions ---
        batch_size_latent, channels, height_latent, width_latent = latent_samples.shape
        height_pixel = height_latent * 8
        width_pixel = width_latent * 8

        print(f"Input dimensions: {width_pixel}x{height_pixel} pixels ({width_latent}x{height_latent} latent)")

        # --- Calculate Tile Parameters ---
        x_slices, y_slices, tile_w_pixel, tile_h_pixel, overlap_pixel = self.calculate_tile_params(
            width_pixel, height_pixel, max_tile_size, overlap_size
        )
        tile_w_latent = tile_w_pixel // 8
        tile_h_latent = tile_h_pixel // 8
        overlap_latent = overlap_pixel // 8

        print(f"Tiling: {x_slices}x{y_slices} slices, Tile Size: {tile_w_pixel}x{tile_h_pixel}px ({tile_w_latent}x{tile_h_latent} latent), Overlap: {overlap_pixel}px ({overlap_latent} latent)")

        # --- Prepare Output Tensor and Blending Mask ---
        output_latent = torch.zeros_like(latent_samples)
        blend_mask = torch.zeros_like(latent_samples) # Tracks contribution count for averaging

        # Create a linear feathering mask for blending overlaps
        feather_margin = overlap_latent
        feather_mask_x = torch.ones((1, 1, 1, tile_w_latent), device=device)
        feather_mask_y = torch.ones((1, 1, tile_h_latent, 1), device=device)

        if overlap_latent > 0:
            # Clamp the effective margin to avoid indexing errors if overlap > tile dimension
            effective_margin_x = min(feather_margin, tile_w_latent)
            effective_margin_y = min(feather_margin, tile_h_latent)

            # Linear ramp from 0 to 1 over the overlap margin
            # Apply to X mask (width)
            for i in range(effective_margin_x): # Iterate up to tile_w_latent (exclusive)
                # Ensure weight calculation uses the original feather_margin if possible,
                # but prevent division by zero if feather_margin is 0 (already handled by if overlap_latent > 0)
                weight = (i + 1) / float(feather_margin + 1)
                if i < tile_w_latent: # Check bounds for safety
                    feather_mask_x[..., i] = min(feather_mask_x[..., i], weight) # Left edge
                if -(i + 1) >= -tile_w_latent: # Check bounds for safety
                    feather_mask_x[..., -(i + 1)] = min(feather_mask_x[..., -(i + 1)], weight) # Right edge

            # Apply to Y mask (height)
            for i in range(effective_margin_y): # Iterate up to tile_h_latent (exclusive)
                weight = (i + 1) / float(feather_margin + 1)
                if i < tile_h_latent: # Check bounds for safety
                    feather_mask_y[..., i, :] = min(feather_mask_y[..., i, :], weight) # Top edge
                if -(i + 1) >= -tile_h_latent: # Check bounds for safety
                    feather_mask_y[..., -(i + 1), :] = min(feather_mask_y[..., -(i + 1), :], weight) # Bottom edge

        tile_feather_mask = feather_mask_y * feather_mask_x # Combine X and Y masks

        # --- Tiling Loop ---
        pbar = comfy.utils.ProgressBar(x_slices * y_slices)
        step_x_latent = tile_w_latent - overlap_latent
        step_y_latent = tile_h_latent - overlap_latent

        for y in range(y_slices):
            for x in range(x_slices):
                # Calculate tile boundaries
                y_start_latent = y * step_y_latent
                x_start_latent = x * step_x_latent

                # Ensure tile doesn't go out of bounds (adjust start for last tiles)
                if y_start_latent + tile_h_latent > height_latent:
                    y_start_latent = height_latent - tile_h_latent
                if x_start_latent + tile_w_latent > width_latent:
                    x_start_latent = width_latent - tile_w_latent

                y_end_latent = y_start_latent + tile_h_latent
                x_end_latent = x_start_latent + tile_w_latent

                print(f"  Processing tile ({y+1}/{y_slices}, {x+1}/{x_slices}): Latent Region [{y_start_latent}:{y_end_latent}, {x_start_latent}:{x_end_latent}]")

                # Extract TILE latent tensor slice (already on device)
                tile_latent_tensor = latent_samples[:, :, y_start_latent:y_end_latent, x_start_latent:x_end_latent]

                # Extract TILE noise tensor slice (already on device)
                tile_noise = noise[:, :, y_start_latent:y_end_latent, x_start_latent:x_end_latent]

                # Deep copy conditioning lists for this specific tile call and ensure tensors are on device
                tile_positive = prepare_cond_for_tile(positive, device)
                tile_negative = prepare_cond_for_tile(negative, device)

                # Removed the check for use_sliced_conditioning as the option is removed.
                # The code now always uses the full conditioning for each tile.

                # --- Perform Sampling on Tile ---
                # Note: We might need to adjust seed per tile if desired, or use the main seed
                tile_seed = seed # For now, use the same seed for all tiles
                if control_after_generate == 'increment':
                    seed += 1
                elif control_after_generate == 'decrement':
                    seed -= 1
                elif control_after_generate == 'randomize': # Correct indentation
                    # Use max signed int64 as the upper bound to avoid overflow
                     seed = np.random.randint(0, 0x7fffffffffffffff)


                # tile_noise is already on the device from the prepare_noise call + .to(device)
                # tile_positive and tile_negative are fresh deep copies for this tile

                # Pass the CLONED model, TILE noise slice, COPIED conditioning lists, and the TILE LATENT TENSOR itself to comfy.sample.sample
                sampled_output = comfy.sample.sample(model_copy, tile_noise, steps, cfg, sampler_name, scheduler, # Use CLONED model, TILE noise
                                                     tile_positive, tile_negative, tile_latent_tensor, # Pass COPIED cond, TILE latent tensor
                                                     denoise=denoise, disable_noise=False, start_step=None,
                                                     last_step=None, force_full_denoise=False, noise_mask=None,
                                                     callback=None, disable_pbar=True, seed=tile_seed) # Disable inner pbar

                # --- Blend Tile into Output ---
                # Handle output (might be tensor or dict) and apply feather mask
                if torch.is_tensor(sampled_output):
                    sampled_tile_tensor = sampled_output
                elif isinstance(sampled_output, dict) and "samples" in sampled_output and torch.is_tensor(sampled_output["samples"]):
                    sampled_tile_tensor = sampled_output["samples"]
                else: # Corrected indentation
                    raise TypeError(f"comfy.sample.sample did not return a tensor or a dict with a 'samples' tensor, but {type(sampled_output)}") # Corrected indentation

                # Ensure the sampled tensor is on the correct device before multiplying with the mask
                sampled_tile_tensor = sampled_tile_tensor.to(device)
                feathered_tile = sampled_tile_tensor * tile_feather_mask

                # Add feathered tile tensor to the corresponding region in the output
                output_latent[:, :, y_start_latent:y_end_latent, x_start_latent:x_end_latent] += feathered_tile
                # Add the feather mask itself to the blend_mask to track contributions (Corrected Indentation)
                blend_mask[:, :, y_start_latent:y_end_latent, x_start_latent:x_end_latent] += tile_feather_mask

                pbar.update(1)


        # --- Finalize Output ---
        # Avoid division by zero by clamping blend_mask where it's zero
        blend_mask = torch.clamp(blend_mask, min=1e-6)
        # Average the contributions in overlapping areas
        final_latent_samples = output_latent / blend_mask
        final_latent_samples = final_latent_samples.to(comfy.model_management.intermediate_device())

        # --- Decode Final Latent ---
        final_latent = {"samples": final_latent_samples}
        # VAE decode should handle device placement internally
        # vae.to(model.load_device) # Removed this line causing AttributeError
        image_out = vae.decode(final_latent["samples"])
        image_out = image_out.to(comfy.model_management.intermediate_device())


        # --- Return Outputs ---
        # Ensure latent is on CPU if it's an output
        final_latent["samples"] = final_latent["samples"].cpu()

        # Pass through other inputs/outputs
        # Order: model, positive, negative, vae, latent, image
        return (model, positive, negative, vae, final_latent, image_out)

# Note: NODE_CLASS_MAPPINGS and NODE_DISPLAY_NAME_MAPPINGS
# will be updated in __init__.py later.
