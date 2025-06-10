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

import math

class HolafSliceCalculator:
    """
    Calculates the number of horizontal and vertical slices (tiles) needed to
    cover a large image, based on a maximum tile size and a pixel overlap.
    This node provides the slice counts and effective overlap percentage, which is
    useful for configuring tiling or upscaling workflows.
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "Width": ("INT", {"default": 1280, "min": 64, "max": 8192, "step": 8}),
                "Height": ("INT", {"default": 1280, "min": 64, "max": 8192, "step": 8}),
                # The maximum size a single tile can be (e.g., model's native resolution).
                "Max_Tile_Size": ("INT", {"default": 1280, "min": 64, "max": 8192, "step": 8}),
                # How many pixels adjacent tiles should share to blend seams.
                "Overlap": ("INT", {"default": 96, "min": 0, "max": 8192, "step": 8}),
            },
        }

    RETURN_TYPES = ("INT", "INT", "FLOAT", "STRING")
    RETURN_NAMES = ("X Slices", "Y Slices", "Overlap Percent", "Summary")
    FUNCTION = "calculate_slices"
    CATEGORY = "Holaf"

    def calculate_slices(self, Width, Height, Max_Tile_Size, Overlap):
        """
        Calculates the number of slices needed and the effective overlap percentage.
        """
        # Clamp overlap to be less than the max tile size to prevent invalid calculations.
        Overlap = min(Overlap, Max_Tile_Size - 8) if Max_Tile_Size > 8 else 0

        # Determine the initial dimensions of a single processing tile.
        tile_w = min(Width, Max_Tile_Size)
        tile_h = min(Height, Max_Tile_Size)

        # Calculate the effective distance to advance for each new tile.
        step_w = tile_w - Overlap
        step_h = tile_h - Overlap

        # Calculate the number of slices required for each dimension.
        if tile_w >= Width or step_w <= 0:
            x_slices = 1
        else:
            # The count is 1 (for the first tile) plus enough tiles to cover the remaining area.
            # math.ceil ensures that even a small remainder gets a full new tile.
            x_slices = 1 + math.ceil((Width - tile_w) / step_w)

        if tile_h >= Height or step_h <= 0:
            y_slices = 1
        else:
            y_slices = 1 + math.ceil((Height - tile_h) / step_h)

        nb_tiles = x_slices * y_slices

        # For a more accurate summary, calculate the ideal tile dimensions that would
        # be required for a perfect grid fit with the determined slice count and overlap.
        # These values are used for display purposes, not for the core slice count logic.
        final_tile_w = Width if x_slices == 1 else math.ceil((Width + (x_slices - 1) * Overlap) / float(x_slices))
        final_tile_h = Height if y_slices == 1 else math.ceil((Height + (y_slices - 1) * Overlap) / float(y_slices))

        # Calculate the final overlap as a percentage of the smaller final tile dimension.
        min_final_tile_dim = min(final_tile_w, final_tile_h)
        if min_final_tile_dim > 0:
            effective_overlap = max(0, min(Overlap, min_final_tile_dim))
            final_overlap_percent = (effective_overlap / float(min_final_tile_dim)) * 100.0
        else:
            final_overlap_percent = 0.0

        # Create a human-readable summary string for display in the UI.
        result_string = f"{x_slices}x{y_slices} ({nb_tiles}) {int(final_tile_w)}x{int(final_tile_h)}px Ovlp:{final_overlap_percent:.1f}%"

        # Return the calculated values in the expected format.
        return (int(x_slices), int(y_slices), round(final_overlap_percent, 2), result_string)