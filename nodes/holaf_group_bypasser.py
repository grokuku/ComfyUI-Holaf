from .holaf_bypasser import ANY_TYPE

class HolafGroupBypasser:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # MODIFICATION CRITIQUE :
                # On passe de (["None"],) à ("STRING", ...)
                # Cela transforme l'entrée en "Texte libre" pour le validateur Python,
                # ce qui accepte n'importe quel nom de groupe ("Step 1", "Step 2", etc.).
                # Le JavaScript se chargera de l'afficher comme une Dropdown.
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

    # On garde VALIDATE_INPUTS par sécurité
    @classmethod
    def VALIDATE_INPUTS(s, **kwargs):
        return True

    def check_lazy_status(self, comfy_group, group_name, active, bypass_mode, original=None, alternative=None, **kwargs):
        """
        Gère l'évaluation paresseuse pour éviter les erreurs "Missing Input" 
        quand le groupe source est coupé.
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