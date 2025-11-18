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
import comfy.sd
import comfy.model_management
from nodes import ConditioningCombine # Import the core ConditioningCombine node

class HolafZoneConditioner:
    """
    A user-friendly node for regional conditioning.
    It allows applying different prompts to 3 rectangular zones on top of a global prompt.
    The zones are interactively defined in the UI.
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
                # The zone data will be passed from the frontend widget as a JSON string
                "zones": ("STRING", {'''default''': '''[{"x": 50, "y": 50, "width": 200, "height": 200}, {"x": 300, "y": 300, "width": 200, "height": 200}, {"x": 550, "y": 550, "width": 200, "height": 200}]''', "widget": "hidden"}),
            }
        }

    RETURN_TYPES = ("CONDITIONING",)
    FUNCTION = "generate_conditioning"
    CATEGORY = "Holaf"

    def generate_conditioning(self, clip: CLIP, width: int, height: int, prompt_global: str, prompt_zone_1: str, prompt_zone_2: str, prompt_zone_3: str, zones: str):
        
        # --- 1. Encode the global prompt ---
        tokens = clip.tokenize(prompt_global)
        base_cond, base_pooled = clip.encode_from_tokens(tokens, return_pooled=True)
        final_cond = [[base_cond, {"pooled_output": base_pooled}]]

        # --- 2. Parse zone data from the frontend ---
        try:
            zone_data = json.loads(zones)
        except Exception as e:
            print(f"[HolafZoneConditioner] Warning: Could not parse zone data. Returning global prompt only. Error: {e}")
            return (final_cond, )

        zone_prompts = [prompt_zone_1, prompt_zone_2, prompt_zone_3]
        combiner = ConditioningCombine()

        # --- 3. Process each zone ---
        for i, zone in enumerate(zone_data):
            prompt_text = zone_prompts[i].strip()
            if not prompt_text:
                continue # Skip if the zone prompt is empty

            # --- 4. Create additive prompt and encode it ---
            additive_prompt = f"{prompt_global}, {prompt_text}"
            print(f"[HolafZoneConditioner] Applying prompt for Zone {i+1}: '{prompt_text}'")

            zone_tokens = clip.tokenize(additive_prompt)
            zone_cond, zone_pooled = clip.encode_from_tokens(zone_tokens, return_pooled=True)

            # --- 5. Create the mask for the zone ---
            downscale_factor = 8
            mask = torch.zeros([1, height // downscale_factor, width // downscale_factor])
            x = zone['x'] // downscale_factor
            y = zone['y'] // downscale_factor
            mask_width = zone['width'] // downscale_factor
            mask_height = zone['height'] // downscale_factor
            mask[:, y:y+mask_height, x:x+mask_width] = 1.0

            # --- 6. Create the zone's conditioning with the mask ---
            zone_conditioning = [[zone_cond, {"pooled_output": zone_pooled, "mask": mask, "strength": 1.0}]]

            # --- 7. Combine it with the main conditioning ---
            final_cond = combiner.combine(final_cond, zone_conditioning)[0]

        return (final_cond, )

# This mapping is used by __init__.py to register the node with ComfyUI.
NODE_CLASS_MAPPINGS = {
  'HolafZoneConditioner': HolafZoneConditioner,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'HolafZoneConditioner': "Zone Conditioner (Holaf)",
}
