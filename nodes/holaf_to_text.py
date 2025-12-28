import torch

# Utility class to accept any input type
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

class HolafToText:
    """
    Accepts any input, converts it to string, displays it on the node,
    and passes the original input through.
    """
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "any_input": (AnyType("*"),),
            },
        }

    RETURN_TYPES = (AnyType("*"), "STRING")
    RETURN_NAMES = ("original", "text")
    FUNCTION = "run"
    OUTPUT_NODE = True
    CATEGORY = "Holaf/Utils"

    def run(self, any_input):
        # Convert input to string representation
        try:
            # Handle specific types for cleaner output if needed
            if isinstance(any_input, torch.Tensor):
                text_val = f"Tensor shape: {any_input.shape}"
            else:
                text_val = str(any_input)
        except Exception as e:
            text_val = f"Error converting to text: {e}"

        # Return:
        # 1. "ui": Data to be sent to the Javascript frontend (the text to display)
        # 2. "result": The actual outputs connected to other nodes
        return {"ui": {"text": [text_val]}, "result": (any_input, text_val)}