from .holaf_utils import AnyType


class HolafAutoSelectX2:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        any_type = AnyType("*")
        return {
            "required": {},
            "optional": {
                "input_1": (any_type,),
                "input_2": (any_type,),
            }
        }

    RETURN_TYPES = (AnyType("*"),)
    RETURN_NAMES = ("selected",)
    FUNCTION = "select"
    CATEGORY = "Holaf Custom Nodes/Flow Control"

    def select(self, input_1=None, input_2=None):
        # Priority to input_1
        if input_1 is not None:
            return (input_1,)
        if input_2 is not None:
            return (input_2,)
        
        # If no input is provided, return None
        return (None,)