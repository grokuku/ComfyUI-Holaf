import torch

class HolafVerticalReroute:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {},
            "optional": {
                "in_left": ("*",),
                "in_top": ("*",),
                "in_right": ("*",),
            }
        }

    RETURN_TYPES = ("*",)
    FUNCTION = "route"

    CATEGORY = "Holaf/Utils"

    def route(self, in_left=None, in_top=None, in_right=None):
        # On priorise les entrées : Top > Left > Right
        # Si aucune entrée, on renvoie None (ce qui peut planter la node suivante, mais c'est normal pour un reroute vide)
        if in_top is not None:
            return (in_top,)
        if in_left is not None:
            return (in_left,)
        if in_right is not None:
            return (in_right,)
        
        # Fallback
        return (None,)