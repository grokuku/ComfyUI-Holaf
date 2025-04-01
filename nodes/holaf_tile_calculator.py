# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-01
#
# Purpose:
# This file defines the 'HolafTileCalculator' custom node for ComfyUI.
# Its primary function is to calculate optimal tiling parameters for processing
# a large image (defined by 'Width' and 'Height') in smaller chunks (tiles).
# Given a 'Max_Tile_Size' constraint and a desired 'Overlap' between tiles,
# it determines the total number of tiles needed and the precise 'Tile Width'
# and 'Tile Height' required to perfectly cover the original image dimensions
# while respecting the overlap.
#
# Design Choices & Rationale:
# - Focus on Precise Tile Dimensions: Unlike a node that might just output
#   slice counts, this node calculates the *exact* tile dimensions needed for
#   a seamless reconstruction when using the specified overlap.
# - Input Parameters: Takes image dimensions, maximum tile size, and overlap
#   pixels as input.
# - Calculation Logic:
#   1. Determines the initial number of slices needed horizontally (`x_slices`)
#      and vertically (`y_slices`) based on the `Max_Tile_Size` and `Overlap`.
#      Handles edge cases where overlap is too large or the image fits in one tile.
#   2. Calculates the total number of tiles (`nb_tiles = x_slices * y_slices`).
#   3. Calculates the *final* required tile dimensions (`final_tile_w`, `final_tile_h`)
#      using the formula `D = ceil((A + (N - 1) * C) / N)`, where D is the final
#      tile dimension, A is the total image dimension, N is the number of slices
#      in that dimension, and C is the overlap. Using `math.ceil` ensures each
#      tile is large enough to cover its portion plus the necessary overlap for
#      a perfect fit across the entire image.
#   4. Calculates the effective overlap percentage based on these final, calculated
#      tile dimensions for inclusion in the summary.
# - Outputs: Provides the total number of tiles (`Nb Tiles`), the calculated
#   `Tile Width`, the calculated `Tile Height`, and a concise `Summary` string
#   (e.g., "2x3 (6) 704x704px Ovlp:12.8%").
# - Relationship to Slice Calculator: This node shares core calculation logic with
#   `holaf_slice_calculator.py` but differs in its primary outputs, focusing on
#   the total tile count and the calculated tile dimensions needed for processing,
#   rather than just the slice counts per axis.
# === End Documentation ===

import math

class HolafTileCalculator:
    """
    Calculates tiling parameters based on input dimensions, max tile size, and overlap.
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        """
        Input Types
        """
        return {
            "required": {
                "Width": ("INT", {"default": 1280, "min": 64, "max": 8192, "step": 8}),
                "Height": ("INT", {"default": 1280, "min": 64, "max": 8192, "step": 8}),
                "Max_Tile_Size": ("INT", {"default": 1280, "min": 64, "max": 8192, "step": 8, "display": "number"}), # Added display hint
                "Overlap": ("INT", {"default": 96, "min": 0, "max": 8192, "step": 8, "display": "number"}), # Added display hint
            },
        }

    # Updated outputs for Tile Calculator
    RETURN_TYPES = ("INT", "INT", "INT", "STRING")
    RETURN_NAMES = ("Nb Tiles", "Tile Width", "Tile Height", "Summary")
    FUNCTION = "calculate_tiles"
    CATEGORY = "Holaf"

    def calculate_tiles(self, Width, Height, Max_Tile_Size, Overlap):
        """
        Performs the tile calculation.
        """
        # Clamp overlap to be less than max_tile_size to avoid issues
        Overlap = min(Overlap, Max_Tile_Size - 8) if Max_Tile_Size > 8 else 0

        tile_w = min(Width, Max_Tile_Size)
        tile_h = min(Height, Max_Tile_Size)

        # Prevent division by zero or negative values if overlap equals or exceeds tile dimensions
        step_w = tile_w - Overlap
        step_h = tile_h - Overlap

        if tile_w >= Width: # Use >= to handle edge case where Width equals Max_Tile_Size
            x_slices = 1
        elif step_w <= 0: # If overlap is too large, only one slice is possible
             x_slices = 1
        else:
            # Calculate slices needed. Add 1 because the first tile covers the start.
            x_slices = 1 + math.ceil((Width - tile_w) / step_w)


        if tile_h >= Height: # Use >= to handle edge case where Height equals Max_Tile_Size
            y_slices = 1
        elif step_h <= 0: # If overlap is too large, only one slice is possible
            y_slices = 1
        else:
             # Calculate slices needed. Add 1 because the first tile covers the start.
            y_slices = 1 + math.ceil((Height - tile_h) / step_h)


        nb_tiles = x_slices * y_slices

        # Calculate overlap percentage based on the smaller dimension of the actual tile size used
        min_tile_dim = min(tile_w, tile_h)
        if min_tile_dim > 0:
             # Ensure overlap doesn't exceed the tile dimension for percentage calculation
            effective_overlap = min(Overlap, min_tile_dim)
            overlap_percent = (effective_overlap / min_tile_dim) * 100.0
        else:
            overlap_percent = 0.0 # Avoid division by zero

        # Ensure slices are at least 1 (should be guaranteed by logic above, but as safeguard)
        x_slices = max(1, int(x_slices))
        y_slices = max(1, int(y_slices))

        # Calculate the precise tile size needed for perfect fit using the formula: D = (A + (N - 1) * C) / N
        if x_slices == 1:
            final_tile_w = Width
        else:
            # Use floating point division for accuracy before ceiling
            ideal_tile_w = (Width + (x_slices - 1) * Overlap) / float(x_slices)
            final_tile_w = math.ceil(ideal_tile_w)

        if y_slices == 1:
            final_tile_h = Height
        else:
            # Use floating point division for accuracy before ceiling
            ideal_tile_h = (Height + (y_slices - 1) * Overlap) / float(y_slices)
            final_tile_h = math.ceil(ideal_tile_h)

        # Ensure final tile dimensions are integers
        final_tile_w = int(final_tile_w)
        final_tile_h = int(final_tile_h)

        # Recalculate overlap percentage based on the final calculated tile dimensions
        min_final_tile_dim = min(final_tile_w, final_tile_h)
        if min_final_tile_dim > 0:
            # Ensure overlap doesn't exceed the final tile dimension for percentage calculation
            # Also ensure overlap isn't negative
            effective_overlap = max(0, min(Overlap, min_final_tile_dim))
            overlap_percent = (effective_overlap / float(min_final_tile_dim)) * 100.0
        else:
            overlap_percent = 0.0 # Avoid division by zero


        # Format the results string for the summary output
        result_string = f"{x_slices}x{y_slices} ({nb_tiles}) {final_tile_w}x{final_tile_h}px Ovlp:{overlap_percent:.1f}%"

        # Return only Nb Tiles, Tile Width, Tile Height, and Summary
        return (nb_tiles, final_tile_w, final_tile_h, result_string)

# Mappings are handled in __init__.py
