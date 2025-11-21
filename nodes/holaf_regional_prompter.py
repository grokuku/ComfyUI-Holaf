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
import json
from comfy.sd import CLIP
import comfy.model_management

class HolafRegionalPrompter:
    """
    Prepares regional conditioning data for the HolafRegionalSampler node.
    This node encodes prompts and creates a complex attention mask required for
    regional prompting with FLUX models.
    """
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "clip": ("CLIP",),
                "width": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "height": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "prompt_global": ("STRING", {"multiline": True, "default": "masterpiece, best quality"}),
                "prompt_zone_1": ("STRING", {"multiline": True, "default": ""}),
                "prompt_zone_2": ("STRING", {"multiline": True, "default": ""}),
                "prompt_zone_3": ("STRING", {"multiline": True, "default": ""}),
                "zones": ("STRING", {'''default''': '''[{"x":50,"y":50,"width":200,"height":200},{"x":300,"y":300,"width":200,"height":200},{"x":550,"y":550,"width":200,"height":200}]''', "widget": "hidden"}),
            }
        }

    RETURN_TYPES = ("REGIONAL_DATA",)
    FUNCTION = "prepare_regional_data"
    CATEGORY = "Holaf"

    def prepare_regional_data(self, clip: CLIP, width: int, height: int, prompt_global: str, prompt_zone_1: str, prompt_zone_2: str, prompt_zone_3: str, zones: str):
        device = comfy.model_management.get_torch_device()
        
        # --- 1. Encode global prompt and prepare IDs ---
        global_tokens = clip.tokenize(prompt_global)
        global_cond, global_pooled = clip.encode_from_tokens(global_tokens, return_pooled=True)
        
                # The reference pipeline expects concatenated text_ids from both tokenizers for FLUX
                if 'g' in global_tokens and 'l' in global_tokens:
                    # This is a FLUX-style dual CLIP
                    global_text_ids = torch.cat([global_tokens['l'], global_tokens['g']], dim=-1).to(device)
                elif 'l' in global_tokens:
                    # This is likely a standard single CLIP
                    print("[HolafRegionalPrompter] Warning: Single CLIP detected. This node is designed for FLUX and may not work as expected.")
                    global_text_ids = global_tokens['l'].to(device)
                else:
                    raise TypeError("Unsupported token structure from CLIP. This node requires a FLUX-compatible dual CLIP model.")
        
                latent_image_ids = torch.zeros(1, 64, dtype=torch.int32, device=device)
        # --- 2. Parse zone data and encode regional prompts ---
        try:
            zone_data = json.loads(zones)
        except Exception as e:
            zone_data = []

        regional_prompts = [prompt_zone_1, prompt_zone_2, prompt_zone_3]
        regional_conds_list = []
        has_regional = False
        
        for i, prompt_text in enumerate(regional_prompts):
            if prompt_text.strip():
                has_regional = True
                tokens = clip.tokenize(prompt_text.strip())
                cond, _ = clip.encode_from_tokens(tokens, return_pooled=True)
                regional_conds_list.append({"conditioning": cond, "zone_info": zone_data[i]})

        # --- If no regional prompts, return a simpler bundle ---
        if not has_regional:
            regional_data_bundle = {
                "is_regional": False,
                "global_cond": global_cond,
                "global_pooled": global_pooled,
                "global_text_ids": global_text_ids,
                "latent_image_ids": latent_image_ids,
            }
            return (regional_data_bundle,)

        # --- 3. Prepare masks and combined embeddings ---
        conds = [global_cond]
        masks = []
        H, W = height // 8, width // 8
        hidden_seq_len = H * W

        for regional_data in regional_conds_list:
            conds.append(regional_data["conditioning"])
            zone = regional_data["zone_info"]
            mask = torch.zeros((1, 1, height, width), device=device)
            mask[:, :, zone['y']:zone['y']+zone['height'], zone['x']:zone['x']+zone['width']] = 1.0
            resized_mask = torch.nn.functional.interpolate(mask, size=(H, W), mode='nearest-exact')
            masks.append(resized_mask.flatten().unsqueeze(1))

        combined_conds = torch.cat(conds, dim=1)
        encoder_seq_len = combined_conds.shape[1]

        # --- 4. Build the final attention mask ---
        regional_attention_mask = torch.zeros(
            (encoder_seq_len + hidden_seq_len, encoder_seq_len + hidden_seq_len),
            device=device,
            dtype=torch.bool
        )

        num_of_regions = len(masks)
        global_prompt_seq_len = global_cond.shape[1]
        each_regional_prompt_seq_len = (encoder_seq_len - global_prompt_seq_len) // num_of_regions

        regional_attention_mask[:global_prompt_seq_len, :] = True
        regional_attention_mask[encoder_seq_len:, :global_prompt_seq_len] = True

        current_pos = global_prompt_seq_len
        for i in range(num_of_regions):
            region_mask_flat = masks[i].repeat(1, each_regional_prompt_seq_len)
            regional_attention_mask[current_pos:current_pos+each_regional_prompt_seq_len, current_pos:current_pos+each_regional_prompt_seq_len] = True
            regional_attention_mask[current_pos:current_pos+each_regional_prompt_seq_len, encoder_seq_len:] = region_mask_flat.transpose(-1, -2)
            regional_attention_mask[encoder_seq_len:, current_pos:current_pos+each_regional_prompt_seq_len] = region_mask_flat
            current_pos += each_regional_prompt_seq_len

        # --- 5. Package data for the sampler ---
        regional_data_bundle = {
            "is_regional": True,
            "global_cond": global_cond,
            "global_pooled": global_pooled,
            "global_text_ids": global_text_ids,
            "latent_image_ids": latent_image_ids,
            "regional_conds": combined_conds,
            "regional_attention_mask": regional_attention_mask,
        }

        return (regional_data_bundle,)

