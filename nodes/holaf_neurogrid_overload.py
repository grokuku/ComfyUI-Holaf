class HolafNeurogridOverload:
    """
    A node that does nothing except print "haha" to the console.
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        """
        Input Types
        """
        return {
            "required": {},
        }

    RETURN_TYPES = () # No output connections
    FUNCTION = "do_nothing_but_print"
    OUTPUT_NODE = True
    CATEGORY = "Holaf"

    def do_nothing_but_print(self):
        """
        Prints "haha" to the console and returns nothing.
        """
        print("haha")
        return () # Must return a tuple, even if empty

# Mappings are now handled in __init__.py
# print("✅ Holaf NeurogridOverload Node loaded") # Optional: remove print statement
