class HolafRemote:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "group_name": ("STRING", {"default": "Group A"}),
                "active": ("BOOLEAN", {"default": False, "label_on": "Active", "label_off": "Inactive"}),
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "process"
    CATEGORY = "holaf"
    OUTPUT_NODE = True

    def process(self, group_name, active):
        # This node does nothing on the backend. 
        # It serves as a UI controller via JavaScript.
        return {}