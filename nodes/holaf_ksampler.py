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


# Renamed class
class HolafKSampler:
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
                # "control_after_generate": (["fixed", "increment", "decrement", "randomize"], {"default": "randomize"}), # Removed duplicate
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1, "round": 0.01}),
                "sampler_name": (samplers,),
                "scheduler": (schedulers,),
                "denoise": ("FLOAT", {"default": 1.00, "min": 0.0, "max": 1.0, "step": 0.01}),
                "input_type": (["latent", "image"], {"default": "latent"}),
                # Removed tiling inputs
                # "max_tile_size": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                # "overlap_size": ("INT", {"default": 128, "min": 0, "max": 8192, "step": 8}),
            },
            "optional": {
                 "latent_image": ("LATENT",), # Optional now, required if input_type is latent
                 "image": ("IMAGE",),       # Optional now, required if input_type is image
            }
        }

    RETURN_TYPES = ("MODEL", "CONDITIONING", "CONDITIONING", "VAE", "LATENT", "IMAGE")
    RETURN_NAMES = ("model", "positive", "negative", "vae", "latent", "image")
    FUNCTION = "sample" # Renamed function
    CATEGORY = "Holaf"

    # Removed calculate_tile_params function

    # Renamed function and removed tiling parameters
    def sample(self, model: ModelPatcher, positive, negative, vae,
                     seed, steps, cfg, sampler_name, scheduler, denoise,
                     input_type, # Removed max_tile_size, overlap_size
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

        # Prepare conditioning on the correct device
        positive_copy = prepare_cond_for_tile(positive, device) # Use the helper, name is okay
        negative_copy = prepare_cond_for_tile(negative, device) # Use the helper, name is okay

        # Clone the model
        model_copy = model.clone()

        # --- Perform Standard Sampling ---
        # Use the prepared noise, conditioning, and latent samples directly
        sampled_output = comfy.sample.sample(model_copy, noise, steps, cfg, sampler_name, scheduler,
                                             positive_copy, negative_copy, latent_samples, # Use prepared inputs
                                             denoise=denoise, disable_noise=False, start_step=None,
                                             last_step=None, force_full_denoise=False, noise_mask=None,
                                             callback=None, disable_pbar=False, seed=seed) # Enable pbar for single sample

        # --- Handle Output ---
        if torch.is_tensor(sampled_output):
            final_latent_samples = sampled_output
        elif isinstance(sampled_output, dict) and "samples" in sampled_output and torch.is_tensor(sampled_output["samples"]):
            final_latent_samples = sampled_output["samples"]
        else:
            raise TypeError(f"comfy.sample.sample did not return a tensor or a dict with a 'samples' tensor, but {type(sampled_output)}")

        final_latent_samples = final_latent_samples.to(comfy.model_management.intermediate_device())

        # --- Decode Final Latent ---
        final_latent = {"samples": final_latent_samples}
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
