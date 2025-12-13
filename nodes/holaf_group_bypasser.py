from .holaf_bypasser import ANY_TYPE

class HolafGroupBypasser:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # ComfyUI voit ["None"], mais le JS va injecter les vrais noms.
                # VALIDATE_INPUTS ci-dessous empêchera l'erreur de validation.
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

    # --- CORRECTION DU BUG "Value not in list" ---
    @classmethod
    def VALIDATE_INPUTS(s, input_types):
        # On force la validation à True pour accepter les noms de groupes 
        # qui ne sont pas dans la liste ["None"] définie statiquement.
        return True

    def check_lazy_status(self, comfy_group, group_name, active, bypass_mode, original=None, alternative=None, **kwargs):
        """
        Gère l'évaluation paresseuse (Lazy Evaluation) pour éviter les erreurs 
        quand une entrée est manquante/mute.
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