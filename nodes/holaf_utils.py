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

"""Shared utilities for Holaf nodes."""

import torch


def prepare_cond_for_tile(original_cond_list, device):
    """Shallow copy + tensor clone (faster than deepcopy for large conditionings).

    Note: This uses a shallow dict copy. If any values in the conditioning dict
    are mutable nested objects, they will be shared between copies. This is
    acceptable for ComfyUI conditioning dicts which are not mutated in place.
    """
    if not isinstance(original_cond_list, list):
        return []
    cond_list_copy = []
    for item in original_cond_list:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            if torch.is_tensor(item[0]):
                cloned_tensor = item[0].clone().to(device)
                cond_dict = item[1].copy() if len(item) > 1 and isinstance(item[1], dict) else {}
                cond_list_copy.append([cloned_tensor, cond_dict])
            else:
                cond_list_copy.append(list(item))
        elif torch.is_tensor(item):
            cond_list_copy.append([item.clone().to(device), {}])
        else:
            cond_list_copy.append(item)
    return cond_list_copy


class AnyType(str):
    """A special type that can be any ComfyUI data type.

    Allows a node to accept any input type by overriding type checking.
    The str base class lets us pass type comparisons that expect a string.

    WARNING: __eq__ always returns True and __ne__ always returns False.
    Do NOT use this class in general comparison logic — it is designed
    exclusively for ComfyUI type coercion.
    """

    def __ne__(self, __value: object) -> bool:
        return False

    def __eq__(self, __value: object) -> bool:
        return True

    def __str__(self) -> str:
        return "*"