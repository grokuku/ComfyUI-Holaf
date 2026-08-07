# Copyright (C) 2025 Holaf
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
HolafSimpleBypasser — Reactive bypasser node.

Unlike HolafRemote (which *initiates* group synchronization), this node is a
*reactive* bypasser: it listens for group state changes pushed by the JS layer
via the ``syncGroupState`` mechanism and never initiates synchronization itself.

The node exposes three widgets on the Python side:

* ``group_name`` — the name of the group this node reacts to.
* ``invert``    — when True, the node's ``active`` state is inverted relative
                  to the group's state (i.e. the node is active when the group
                  is OFF and vice-versa).
* ``active``    — stores the current group state received via sync. This widget
                  is declared here for serialization purposes but is **hidden**
                  on the JS side; its value is driven exclusively by
                  ``syncGroupState``.

The node also accepts an optional ``input`` of any type so it can be wired into
the graph as a pass-through / sink.
"""

from .holaf_utils import ANY_TYPE


class HolafSimpleBypasser:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "group_name": ("STRING", {"default": "Group A"}),
                "invert": ("BOOLEAN", {"default": False, "label_on": "Inverted", "label_off": "Normal"}),
                "active": ("BOOLEAN", {"default": False, "label_on": "ON", "label_off": "OFF"}),
            },
            "optional": {
                "input": (ANY_TYPE,),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "process"
    CATEGORY = "Holaf"
    OUTPUT_NODE = True

    def process(self, group_name, invert, active, input=None, **kwargs):
        return {}