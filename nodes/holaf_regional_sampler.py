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
import comfy.sample
import comfy.samplers
import comfy.utils
import latent_preview

class HolafRegionalSampler:
    """
    A custom KSampler that is compatible with the data prepared by the RegionalPrompter node.
    It injects the regional attention mask into the FLUX transformer model during sampling.
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": ("MODEL",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 28, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 4.0, "min": 0.0, "max": 100.0, "step": 0.1, "round": 0.01}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "latent_image": ("LATENT",),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "regional_data": ("REGIONAL_DATA",),
                "mask_inject_steps": ("INT", {"default": 10, "min": 0, "max": 10000}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    FUNCTION = "sample"
    CATEGORY = "Holaf"

    def sample(self, model, seed, steps, cfg, sampler_name, scheduler, latent_image, denoise, regional_data, mask_inject_steps):
        
        # If not regional, fall back to the standard comfy sampler for simplicity and compatibility
        if not regional_data.get("is_regional", False):
            print("[HolafRegionalSampler] No regional data found. Using standard KSampler.")
            positive = [[regional_data["global_cond"], {"pooled_output": regional_data["global_pooled"]}]]
            # Create a dummy negative conditioning
            negative_tokens = model.tokenize("")
            negative_cond, negative_pooled = model.encode_from_tokens(negative_tokens, return_pooled=True)
            negative = [[negative_cond, {"pooled_output": negative_pooled}]]
            return comfy.sample.common_ksampler(model, seed, steps, cfg, sampler_name, "euler", positive, negative, latent_image, denoise=denoise)

        print("[HolafRegionalSampler] Regional data found. Using custom FLUX sampling logic.")

        # --- Unpack Data --- #
        device = model.load_device
        latent = latent_image["samples"].to(device)
        
        global_cond = regional_data["global_cond"].to(device)
        global_pooled = regional_data["global_pooled"].to(device)
        global_text_ids = regional_data["global_text_ids"].to(device)
        latent_image_ids = regional_data["latent_image_ids"].to(device)
        regional_conds = regional_data["regional_conds"].to(device)
        regional_attention_mask = regional_data["regional_attention_mask"].to(device)

        # --- Prepare for Sampling --- #
        noise = torch.manual_seed(seed)
        noise = torch.randn(latent.shape, generator=noise, device=device, dtype=latent.dtype)
        
        # We use the FlowMatchEulerDiscreteScheduler's logic as per the reference
        sigmas = comfy.samplers.get_sigmas_flowmatch(steps + 1, device=device)
        
        guidance = torch.full([latent.shape[0]], cfg, device=device, dtype=torch.float32)
        
        pbar = comfy.utils.ProgressBar(steps)
        previewer = latent_preview.get_previewer(device, model.model.latent_format)

        # --- The Denoising Loop --- #
        for i in range(steps):
            comfy.model_management.throw_exception_if_processing_interrupted()
            
            sigma = sigmas[i]
            timestep = torch.full((latent.shape[0],), sigma * 1000, device=device, dtype=latent.dtype)

            # Determine which conditioning to use for this step
            if i < mask_inject_steps:
                cond_for_step = regional_conds
                attn_mask = regional_attention_mask
                base_ratio = 0.5 # A default base_ratio, can be exposed as a parameter later
            else:
                cond_for_step = global_cond
                attn_mask = None
                base_ratio = None

            # Model prediction call, now with all required arguments
            noise_pred = model.model.diffusion_model(
                hidden_states=latent,
                timestep=timestep,
                guidance=guidance,
                pooled_projections=global_pooled,
                encoder_hidden_states=cond_for_step,
                txt_ids=global_text_ids,
                img_ids=latent_image_ids,
                encoder_hidden_states_base=global_cond,
                base_ratio=base_ratio,
                joint_attention_kwargs={'regional_attention_mask': attn_mask},
            )

            # Scheduler step
            dt = sigmas[i+1] - sigma
            latent = latent + noise_pred * dt

            if previewer is not None:
                previewer.decode_latent_to_preview(latent.to(previewer.device))
            pbar.update(1)

        # Return the final latent
        out = latent_image.copy()
        out["samples"] = latent.to("cpu")
        return (out,)
