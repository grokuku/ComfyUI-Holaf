from .holaf_bypasser import ANY_TYPE

class HolafGroupBypasser:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "comfy_group": (["None"],), 
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
    CATEGORY = "holaf"

    def check_lazy_status(self, comfy_group, group_name, active, bypass_mode, original=None, alternative=None, **kwargs):
        """
        Informe ComfyUI des entrées strictement nécessaires.
        L'ajout de **kwargs est CRITIQUE pour éviter que cette fonction ne crash 
        si ComfyUI envoie des arguments cachés (unique_id, etc.).
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