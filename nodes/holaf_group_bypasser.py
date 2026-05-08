from .holaf_bypasser import ANY_TYPE

class HolafGroupBypasser:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # CRITICAL CHANGE:
                # Switched from (["None"],) to ("STRING", ...)
                # This makes the input a free-text field for the Python validator,
                # accepting any group name ("Step 1", "Step 2", etc.).
                # The JavaScript will render it as a dropdown.
                "comfy_group": ("STRING", {"default": "None"}), 
                "group_name": ("STRING", {"default": "Group A"}),
                "active": ("BOOLEAN", {"default": True, "label_on": "ON", "label_off": "OFF"}),
                "bypass_mode": (["Bypass", "Mute"],),
            },
            "optional": {
                "original": (ANY_TYPE,),
                "alternative": (ANY_TYPE,),
            }
        }

    RETURN_TYPES = (ANY_TYPE,)
    RETURN_NAMES = ("output",)
    FUNCTION = "process"
    CATEGORY = "Holaf"

    # Keep VALIDATE_INPUTS for safety
    @classmethod
    def VALIDATE_INPUTS(s, **kwargs):
        return True

    def check_lazy_status(self, comfy_group, group_name, active, bypass_mode, original=None, alternative=None, **kwargs):
        """Manages lazy evaluation to prevent 'Missing Input' errors
        when the source group is bypassed.
        """
        if active:
            return ["original"]
        else:
            return ["alternative"]

    def process(self, comfy_group, group_name, active, bypass_mode, original=None, alternative=None, **kwargs):
        if active:
            return (original,)
        else:
            return (alternative,)