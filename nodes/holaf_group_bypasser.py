from .holaf_bypasser import ANY_TYPE

class HolafGroupBypasser:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # CHANGEMENT ICI : En mettant une liste entre crochets, 
                # ComfyUI crée nativement une Dropdown List.
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

    def check_lazy_status(self, comfy_group, group_name, active, bypass_mode, original=None, alternative=None):
        """
        Informe ComfyUI des entrées strictement nécessaires pour l'exécution actuelle.
        Si active est False, on ignore l'état de 'original' (qui peut être Mute/Mort),
        ce qui empêche le nœud de passer en erreur.
        """
        if active:
            return ["original"]
        else:
            return ["alternative"]

    def process(self, comfy_group, group_name, active, bypass_mode, original=None, alternative=None):
        if active:
            return (original,)
        else:
            return (alternative,)