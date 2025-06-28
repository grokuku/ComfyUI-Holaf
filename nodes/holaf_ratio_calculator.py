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

class HolafRatioCalculator:
    """
    Calculates all possible resolutions that match a given aspect ratio,
    adhere to a dimension multiple (e.g., divisible by 8), and fall within
    a specified min/max range.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "ratio_width": ("INT", {"default": 16, "min": 1}),
                "ratio_height": ("INT", {"default": 9, "min": 1}),
                "multiple_of": ("INT", {"default": 8, "min": 1}),
                "min_dimension": ("INT", {"default": 512, "min": 1}),
                "max_dimension": ("INT", {"default": 2048, "min": 1, "max": 8162}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("formatted_resolutions",)
    FUNCTION = "calculate_ratios"
    CATEGORY = "Holaf"

    def calculate_ratios(self, ratio_width, ratio_height, multiple_of, min_dimension, max_dimension):
        # --- Input Validation ---
        if min_dimension > max_dimension:
            return ("Error: min_dimension cannot be greater than max_dimension.",)
        if ratio_width <= 0 or ratio_height <= 0 or multiple_of <= 0:
            return ("Error: Ratio dimensions and 'multiple_of' must be positive.",)

        # --- Logic ---
        # 1. Simplify the aspect ratio using the greatest common divisor (GCD).
        #    This gives us the smallest integer pair representing the ratio (e.g., 1920:1080 -> 16:9).
        common_divisor = math.gcd(ratio_width, ratio_height)
        base_w = ratio_width // common_divisor
        base_h = ratio_height // common_divisor

        valid_resolutions = []
        
        # 2. Determine the range of multipliers to check.
        #    We iterate using a multiplier 'k' applied to our base ratio (base_w, base_h).
        #    The start_k ensures the smallest dimension is at least min_dimension.
        #    The end_k ensures the largest dimension does not exceed max_dimension.
        start_k = math.ceil(min_dimension / min(base_w, base_h))
        end_k = math.floor(max_dimension / max(base_w, base_h))

        for k in range(start_k, end_k + 1):
            current_w = k * base_w
            current_h = k * base_h

            # 3. Check if the calculated resolution meets all conditions.
            if (current_w >= min_dimension and current_w <= max_dimension and
                current_h >= min_dimension and current_h <= max_dimension and
                current_w % multiple_of == 0 and
                current_h % multiple_of == 0):
                
                valid_resolutions.append(f"{current_w}x{current_h}")

        # --- Formatting Output ---
        if not valid_resolutions:
            output_string = "No matching resolutions found for the given criteria."
        else:
            output_string = "\n".join(valid_resolutions)
        
        return (output_string,)