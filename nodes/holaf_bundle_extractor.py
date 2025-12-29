# nodes/holaf_bundle_extractor.py

class AnyType(str):
    """A special type that compares equal to any other type.
    Used here to trick ComfyUI validation into accepting any connection.
    """
    def __ne__(self, __value: object) -> bool:
        return False

class HolafBundleExtractor:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "bundle": ("HOLAF_BUNDLE_DATA",),
            }
        }
    
    # We use AnyType("*") for all 20 outputs so they can connect to anything (IMAGE, MODEL, etc.)
    RETURN_TYPES = tuple([AnyType("*")] * 20)
    
    # Names corresponding to the creator inputs for clarity
    RETURN_NAMES = tuple([f"output_{i:02}" for i in range(1, 21)])
    
    FUNCTION = "do_extract"
    CATEGORY = "Holaf Custom Nodes/Flow Control"

    def do_extract(self, bundle):
        """
        Extracts data from the bundle and maps it to the corresponding outputs.
        """
        results = []
        for i in range(1, 21):
            # Key used in the creator node
            key = f"input_{i:02}"
            
            # Retrieve data if present, else None
            val = bundle.get(key, None)
            results.append(val)
        
        return tuple(results)