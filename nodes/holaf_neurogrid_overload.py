# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-01
#
# Purpose:
# This file defines the 'HolafNeurogridOverload' custom node for ComfyUI.
# Despite its complex-sounding name, this node performs a very simple action:
# it prints the string "haha" to the console when executed within a workflow.
# It serves as a terminal node (OUTPUT_NODE = True) and has no inputs or outputs.
#
# Design Choices & Rationale:
# - Simplicity: The node's core logic is minimal, consisting of a single print statement.
# - Terminal Node: Marked as `OUTPUT_NODE = True`, indicating it doesn't pass data
#   to subsequent nodes, suitable for actions with side effects like logging or printing.
# - No Inputs/Outputs: Reflects its role as a simple action trigger rather than
#   a data processing unit.
# - Naming: The name 'NeurogridOverload' appears to be intentionally misleading or
#   humorous, possibly a placeholder or remnant from a debugging session, as the node
#   has no actual relation to neurogrids or overloading anything. Its function is
#   purely to print a fixed message.
# - Category: Placed within the 'Holaf' category for organization.
# === End Documentation ===

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
