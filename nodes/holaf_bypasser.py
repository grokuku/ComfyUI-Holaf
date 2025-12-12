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

    def process(self, group_name, active, original=None, alternative=None, **kwargs):
        # We accept **kwargs to handle dynamic inputs created by JS (bypass_2, bypass_3, etc.)
        # These extra inputs are just for triggering the bypass logic in JS, 
        # they are not used for data flow processing here.
        
        if active:
            return (original,)
        else:
            return (alternative,)