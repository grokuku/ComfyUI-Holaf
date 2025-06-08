import math

class HolafTileCalculator:
    """
    Calculates optimal parameters for tiling a large image.
    This node determines the total number of tiles and the precise
    'Tile Width' and 'Tile Height' needed to perfectly cover the original
    image dimensions given a maximum tile size and overlap.
    """
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "Width": ("INT", {"default": 1280, "min": 64, "max": 8192, "step": 8}),
                "Height": ("INT", {"default": 1280, "min": 64, "max": 8192, "step": 8}),
                # The maximum size for a single processing tile (e.g., model's native resolution).
                "Max_Tile_Size": ("INT", {"default": 1280, "min": 64, "max": 8192, "step": 8}),
                # The desired pixel overlap between adjacent tiles to hide seams.
                "Overlap": ("INT", {"default": 96, "min": 0, "max": 8192, "step": 8}),
            },
        }

    RETURN_TYPES = ("INT", "INT", "INT", "STRING")
    RETURN_NAMES = ("Nb Tiles", "Tile Width", "Tile Height", "Summary")
    FUNCTION = "calculate_tiles"
    CATEGORY = "Holaf"

    def calculate_tiles(self, Width, Height, Max_Tile_Size, Overlap):
        """
        Calculates the total number of tiles and the precise tile dimensions
        required for seamless processing.
        """
        # Clamp overlap to ensure it's smaller than the tile size, preventing invalid logic.
        Overlap = min(Overlap, Max_Tile_Size - 8) if Max_Tile_Size > 8 else 0

        # Determine the initial dimensions of a single processing tile.
        tile_w = min(Width, Max_Tile_Size)
        tile_h = min(Height, Max_Tile_Size)

        # Calculate the effective 'stride' or distance to advance for each new tile.
        step_w = tile_w - Overlap
        step_h = tile_h - Overlap

        # Determine how many tiles are needed to cover each dimension.
        if tile_w >= Width or step_w <= 0:
            x_slices = 1
        else:
            # One for the initial tile, plus enough tiles to cover the remaining area.
            x_slices = 1 + math.ceil((Width - tile_w) / step_w)

        if tile_h >= Height or step_h <= 0:
            y_slices = 1
        else:
            y_slices = 1 + math.ceil((Height - tile_h) / step_h)

        nb_tiles = x_slices * y_slices

        # --- Key Calculation ---
        # Calculate the exact tile dimensions required for a perfect grid fit.
        # This adjusts the tile size so that the grid of tiles, with their overlaps,
        # precisely covers the original image without any gaps or excess.
        final_tile_w = Width if x_slices == 1 else math.ceil((Width + (x_slices - 1) * Overlap) / float(x_slices))
        final_tile_h = Height if y_slices == 1 else math.ceil((Height + (y_slices - 1) * Overlap) / float(y_slices))

        # Calculate the effective overlap percentage for the summary string.
        min_final_tile_dim = min(final_tile_w, final_tile_h)
        if min_final_tile_dim > 0:
            effective_overlap = max(0, min(Overlap, min_final_tile_dim))
            overlap_percent = (effective_overlap / float(min_final_tile_dim)) * 100.0
        else:
            overlap_percent = 0.0

        # Create a human-readable summary string for the UI.
        result_string = f"{x_slices}x{y_slices} ({nb_tiles}) {int(final_tile_w)}x{int(final_tile_h)}px Ovlp:{overlap_percent:.1f}%"

        # Return the primary calculated values for use in a tiling workflow.
        return (nb_tiles, int(final_tile_w), int(final_tile_h), result_string)