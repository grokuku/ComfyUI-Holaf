import torch
import comfy.sd
import comfy.sample
import comfy.model_management
import pickle
import base64

class HolafInternalSampler:
    @classmethod
    def INPUT_TYPES(s):
        return {"required": {
            "checkpoint_name": ("STRING", {"forceInput": True}),
            "sampler_name": (comfy.samplers.KSampler.SAMPLERS,), "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
            "steps": ("INT", {"default": 20}), "cfg": ("FLOAT", {"default": 8.0}),
            "seed": ("INT", {"default": 0}), "denoise": ("FLOAT", {"default": 1.0}),
            "serialized_latent": ("STRING", {"forceInput": True}),
            "serialized_positive": ("STRING", {"forceInput": True}),
            "serialized_negative": ("STRING", {"forceInput": True}),
        }}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "execute"
    CATEGORY = "Holaf/Internal"

    def execute(self, checkpoint_name, sampler_name, scheduler, steps, cfg, seed, denoise,
                serialized_latent, serialized_positive, serialized_negative):
        model, clip, vae, _ = comfy.sd.load_checkpoint_guess_config(checkpoint_name, output_vae=True, output_clip=True)
        latent = {"samples": pickle.loads(base64.b64decode(serialized_latent))}
        positive = pickle.loads(base64.b64decode(serialized_positive))
        negative = pickle.loads(base64.b64decode(serialized_negative))
        device = comfy.model_management.get_torch_device()
        latent_samples = latent['samples'].to(device)
        noise = torch.zeros(latent_samples.size(), dtype=latent_samples.dtype, layout=latent_samples.layout, device="cpu")
        
        # Le KSampler s'attend à ce que le latent soit sur CPU
        samples = comfy.sample.sample(model, noise, steps, cfg, sampler_name, scheduler,
                                            positive, negative, {"samples":latent_samples.cpu()}, denoise=denoise,
                                            disable_noise=True, callback=None, disable_pbar=True, seed=seed)

        image = vae.decode(samples.to(vae.device))
        return (image,)