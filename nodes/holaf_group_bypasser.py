from .holaf_bypasser import ANY_TYPE

class HolafGroupBypasser:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # This string will be converted to a Combo box by JavaScript
                "comfy_group": ("STRING", {"default": "None"}), 
                "group_name": ("STRING", {"default": "Group A"}),
                "active": ("BOOLEAN", {"default": True, "label_on": "ON", "label_off": "OFF"}),
            },
            "optional": {
                "original": (ANY_TYPE,),
                "alternative": (ANY_TYPE,),
            }
        }

    RETURN_TYPES = (ANY_TYPE,)
    RETURN_NAMES = ("output",)
    FUNCTION = "process"
    CATEGORY = "holaf"

    def process(self, comfy_group, group_name, active, original=None, alternative=None):
        if active:
            return (original,)
        else:
            return (alternative,)