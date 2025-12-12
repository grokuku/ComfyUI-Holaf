import torch

class AnyType(str):
    """A special type that compares equal to any other type."""
    def __ne__(self, __value: object) -> bool:
        return False

    def __eq__(self, __value: object) -> bool:
        return True

    def __str__(self):
        return "*"

ANY_TYPE = AnyType("*")

class HolafBypasser:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "group_name": ("STRING", {"default": "Group A"}),
                "bypass": ("BOOLEAN", {"default": False, "label_on": "ON", "label_off": "OFF"}),
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

    def process(self, group_name, bypass, original=None, alternative=None):
        # Note: The actual "bypassing" of the upstream node happens in JavaScript.
        # This backend logic simply routes the correct data downstream.
        
        if bypass:
            # If bypass is ON (True), we return the alternative data
            return (alternative,)
        else:
            # If bypass is OFF (False - default), we pass the original data through
            return (original,)