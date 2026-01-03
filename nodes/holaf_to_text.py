import torch
import json

# Fixes potential "bool object is not callable" issues in some ComfyUI setups
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

class HolafToText:
    """
    Accepts any input, converts it to string, and provides formatting hints
    for the custom Markdown/HTML renderer.
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "any_input": (AnyType("*"),),
                "display_mode": (["Auto", "Plain", "JSON", "Markdown"], {"default": "Auto"}),
            },
        }

    RETURN_TYPES = (AnyType("*"), "STRING")
    RETURN_NAMES = ("original", "text")
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "Holaf/Utils"

    def run(self, any_input, display_mode):
        text_val = ""
        detected_mode = display_mode

        try:
            if isinstance(any_input, torch.Tensor):
                # Robust tensor check
                shape = list(any_input.shape) if hasattr(any_input, 'shape') else "unknown"
                device = str(any_input.device) if hasattr(any_input, 'device') else "unknown"
                dt = str(any_input.dtype) if hasattr(any_input, 'dtype') else "unknown"
                # Markdown formatting for Tensor
                text_val = f"### Tensor Info\n- **Shape**: `{shape}`\n- **Device**: `{device}`\n- **Dtype**: `{dt}`"
                if detected_mode == "Auto":
                    detected_mode = "Markdown"
            elif isinstance(any_input, (dict, list)):
                # JSON formatting
                text_val = json.dumps(any_input, indent=4, ensure_ascii=False)
                if detected_mode == "Auto":
                    detected_mode = "JSON"
            else:
                text_val = str(any_input)
        except Exception as e:
            text_val = f"**Error**: {str(e)}"

        if detected_mode == "Auto":
            # Heuristic for Markdown
            if text_val.strip().startswith(("#", "- ", "**", "###")):
                detected_mode = "Markdown"
            else:
                detected_mode = "Plain"

        return {
            "ui": {"text": [text_val], "mode": [detected_mode]}, 
            "result": (any_input, text_val)
        }