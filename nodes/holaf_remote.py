class HolafRemote:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "group_name": ("STRING", {"default": "Group A"}),
                "active": ("BOOLEAN", {"default": True, "label_on": "ON", "label_off": "OFF"}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "process"
    CATEGORY = "holaf"
    OUTPUT_NODE = True

    def process(self, group_name, active):
        return {}