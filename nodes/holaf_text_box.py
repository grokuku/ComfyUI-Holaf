class HolafTextBox:
    """
    Standard Text Box with an optional input for concatenation.
    Useful for prompts, notes, or combining string data.
    """
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "", "dynamicPrompts": True}),
            },
            "optional": {
                "text_prepend": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("string",)
    FUNCTION = "run"
    CATEGORY = "Holaf/Utils"

    def run(self, text, text_prepend=None):
        result = text
        
        if text_prepend:
            result = text_prepend + result
            
        return (result,)