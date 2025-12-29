# nodes/holaf_bundle_creator.py

class AnyType(str):
    """A special type that compares equal to any other type.
    Used to allow any connection to the inputs.
    """
    def __ne__(self, __value: object) -> bool:
        return False

class HolafBundleCreator:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        # Define the wildcard type
        any_type = AnyType("*")
        
        # Generate 20 optional inputs
        optional_inputs = {}
        for i in range(1, 21):
            optional_inputs[f"input_{i:02}"] = (any_type, )

        return {
            "required": {},
            "optional": optional_inputs
        }

    RETURN_TYPES = ("HOLAF_BUNDLE_DATA",)
    RETURN_NAMES = ("bundle",)
    FUNCTION = "do_bundle"
    CATEGORY = "Holaf Custom Nodes/Flow Control"
    
    def do_bundle(self, **kwargs):
        """
        Collects all provided inputs into a single dictionary (bundle).
        """
        # kwargs contains all inputs that were actually connected and sent data.
        # We simply return this dictionary as the bundle.
        return (kwargs,)