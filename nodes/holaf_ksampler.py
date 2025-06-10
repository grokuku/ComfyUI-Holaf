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
import comfy.samplers
import comfy.utils
import comfy.model_management
import copy

def prepare_cond_for_tile(original_cond_list, device):
    """
    Deep copies a conditioning list and moves all its tensors to the specified device.
    This prevents modifying the original conditioning data and ensures tensors are on the correct
    device for the sampling process.
    """
    if not isinstance(original_cond_list, list):
        return []

    cond_list_copy = copy.deepcopy(original_cond_list)
    for i, item in enumerate(cond_list_copy):
        # Handle the standard conditioning format: [tensor, {dict}]
        if isinstance(item, (list, tuple)) and len(item) >= 1 and torch.is_tensor(item[0]):
            if item[0].device != device:
                cond_list_copy[i][0] = item[0].to(device)
            # Ensure the dictionary part exists.
            if len(item) == 1:
                 cond_list_copy[i].append({})
        # Handle cases where the list contains just a tensor.
        elif torch.is_tensor(item):
            tensor_on_device = item
            if item.device != device:
                 tensor_on_device = item.to(device)
            cond_list_copy[i] = [tensor_on_device, {}]

    return cond_list_copy

class HolafKSampler:
    """
    A wrapper for the core ComfyUI sampler.
    It supports direct image input (which is automatically VAE-encoded),
    provides an option to clear VRAM before sampling, and passes through
    the main components for easy chaining. It also includes a bypass option.
    """
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
                "clean_vram": ("BOOLEAN", {"default": False}),
                "bypass": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                 "latent_image": ("LATENT",),
                 "image": ("IMAGE",),
            }
        }

    RETURN_TYPES = ("MODEL", "CONDITIONING", "CONDITIONING", "VAE", "LATENT", "IMAGE")
    RETURN_NAMES = ("model", "positive", "negative", "vae", "latent", "image")
    FUNCTION = "sample"
    CATEGORY = "Holaf"

    def sample(self, model, positive, negative, vae,
                     seed, steps, cfg, sampler_name, scheduler, denoise,
                     input_type, clean_vram, bypass,
                     latent_image=None, image=None):
        """
        Executes the sampling process, handling input type, device placement, VRAM, and bypass logic.
        """
        # --- Bypass Logic ---
        if bypass:
            print("[HolafKSampler] Bypassing sampling process.")
            # If bypassed, we must return the original inputs to maintain the workflow chain.
            final_latent = latent_image
            image_out = image

            # If input is latent, we need to decode it to get an image for the image output.
            if input_type == "latent" and latent_image is not None:
                if image is None: # Only decode if no image was provided
                    image_out = vae.decode(latent_image["samples"].to(vae.device))
                else: # An image was already provided, just pass it through
                    image_out = image
            
            # If input is an image, we need to encode it to get a latent for the latent output.
            elif input_type == "image" and image is not None:
                if latent_image is None: # Only encode if no latent was provided
                    final_latent = {"samples": vae.encode(image[:,:,:,:3])}
                else: # A latent was already provided, just pass it through
                    final_latent = latent_image

            # Ensure both outputs are valid, creating a dummy if necessary to avoid errors.
            if image_out is None and final_latent is not None:
                image_out = vae.decode(final_latent["samples"].to(vae.device))
            elif final_latent is None and image_out is not None:
                final_latent = {"samples": vae.encode(image_out[:,:,:,:3])}
            elif final_latent is None and image_out is None:
                # Fallback if both inputs are missing
                dummy_latent = {"samples": torch.zeros(1, 4, 64, 64)}
                dummy_image = torch.zeros(1, 512, 512, 3)
                return (model, positive, negative, vae, dummy_latent, dummy_image)
            
            return (model, positive, negative, vae, final_latent, image_out)


        # Optionally clear VRAM to free up memory before the main operation.
        if clean_vram:
            comfy.model_management.soft_empty_cache()

        # --- Input Preparation ---
        if input_type == "latent":
            if latent_image is None:
                raise ValueError("Input type is 'latent', but no latent_image provided.")
            latent = latent_image
        elif input_type == "image":
            if image is None:
                raise ValueError("Input type is 'image', but no image provided.")
            # Encode the input image into latent space using the provided VAE.
            encoded_output = vae.encode(image[:,:,:,:3])
            # Handle different VAE encode return types.
            if isinstance(encoded_output, dict) and "samples" in encoded_output:
                latent = encoded_output
            elif torch.is_tensor(encoded_output):
                latent = {"samples": encoded_output}
            else:
                raise TypeError(f"VAE encode returned unexpected type: {type(encoded_output)}")
        else:
            raise ValueError(f"Unknown input_type: {input_type}")

        if "samples" not in latent or not torch.is_tensor(latent["samples"]):
             raise TypeError("Latent input is not a dictionary with a valid 'samples' tensor.")

        # --- Device Placement ---
        device = model.load_device
        latent_samples = latent["samples"].to(device)
        noise = comfy.sample.prepare_noise(latent_samples, seed, None).to(device)
        # Create safe, device-specific copies of conditioning.
        positive_copy = prepare_cond_for_tile(positive, device)
        negative_copy = prepare_cond_for_tile(negative, device)

        # Clone the model to prevent in-place modifications to the original model patcher.
        model_copy = model.clone()

        # --- Sampling ---
        pbar = comfy.utils.ProgressBar(steps)
        def preview_callback(step, x0, x, total_steps):
            pbar.update(1)

        # Execute the core comfy sampler.
        sampled_output = comfy.sample.sample(model_copy, noise, steps, cfg, sampler_name, scheduler,
                                             positive_copy, negative_copy, latent_samples,
                                             denoise=denoise, disable_noise=False, start_step=None,
                                             last_step=None, force_full_denoise=False, noise_mask=None,
                                             callback=preview_callback, disable_pbar=True, seed=seed)

        # --- Output Handling ---
        # Extract the final latent tensor from the sampler's output.
        if torch.is_tensor(sampled_output):
            final_latent_samples = sampled_output
        elif isinstance(sampled_output, dict) and "samples" in sampled_output:
            final_latent_samples = sampled_output["samples"]
        else:
            raise TypeError(f"comfy.sample.sample returned an unexpected type: {type(sampled_output)}")

        final_latent_samples = final_latent_samples.to(comfy.model_management.intermediate_device())
        final_latent = {"samples": final_latent_samples}

        # Decode the resulting latent into a pixel-space image.
        image_out = vae.decode(final_latent["samples"])
        image_out = image_out.to(comfy.model_management.intermediate_device())

        # Move the final latent to CPU for output to conserve VRAM.
        final_latent["samples"] = final_latent["samples"].cpu()

        # Pass through the original inputs for chaining.
        return (model, positive, negative, vae, final_latent, image_out)