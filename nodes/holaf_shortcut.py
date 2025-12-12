class HolafShortcut:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "shortcut_name": ("STRING", {"default": "Point A", "multiline": False}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "process"
    CATEGORY = "holaf"
    OUTPUT_NODE = True

    def process(self, shortcut_name):
        return {}