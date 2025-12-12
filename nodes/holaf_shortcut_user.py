class HolafShortcutUser:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                # We use a string input that will be matched against shortcut names
                "target_shortcut": ("STRING", {"default": "Point A", "multiline": False}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "process"
    CATEGORY = "holaf"
    OUTPUT_NODE = True

    def process(self, target_shortcut):
        return {}