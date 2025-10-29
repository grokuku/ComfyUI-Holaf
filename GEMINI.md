# GEMINI.md

## Project Overview

This project, "ComfyUI-Holaf," is a collection of custom nodes for ComfyUI, an open-source GUI for Stable Diffusion. These nodes extend ComfyUI's functionality with tools for image manipulation, workflow automation, and performance benchmarking.

The project is primarily written in Python, with JavaScript used for creating interactive frontend widgets for some of the nodes.

Key features based on the file analysis include:

*   **Image Comparison:** An interactive "Image Comparer" node to view two images side-by-side with a slider or click-to-toggle mode.
*   **Advanced KSampler:** A wrapper for ComfyUI's KSampler that adds features like direct image input (auto-encoding), VRAM clearing, and a bypass switch.
*   **Flexible Image Saving:** A "Save Image" node with advanced options for specifying output paths and filenames using date/time formatting, and for saving prompts and workflows as separate text and JSON files.
*   **Benchmarking Tools:** A set of nodes to load models, run benchmarks at different resolutions, and plot the results.
*   **Image Utilities:** Nodes for resizing images for Instagram, overlaying images, and upscaling.
*   **Tiling and Slicing:** Calculators for tiled image processing.
*   **LUT (Look-Up Table) Tools:** Nodes for generating and saving 3D LUTs from reference images.

## Building and Running

This is a plugin for the ComfyUI application.

1.  **Installation:**
    *   Clone this repository into the `ComfyUI/custom_nodes/` directory.

2.  **Dependencies:**
    *   Install the required Python packages using pip:
        ```bash
        pip install -r requirements.txt
        ```
    *   The dependencies are: `numpy`, `Pillow`, `spandrel`, `pandas`, `matplotlib`, `psutil`, `imageio`.

3.  **Running:**
    *   Start or restart the ComfyUI server. The new "Holaf" nodes will be available in the node menu.

## Development Conventions

*   **Licensing:** The project is licensed under the GNU General Public License v3.0. All source files include a license header.
*   **Structure:**
    *   Python node implementations are located in the `nodes/` directory, with each node in its own file.
    *   The main `__init__.py` file registers all the nodes with ComfyUI using `NODE_CLASS_MAPPINGS` and `NODE_DISPLAY_NAME_MAPPINGS`.
    *   JavaScript files for custom UI widgets are in the `js/` directory. The `WEB_DIRECTORY` variable in `__init__.py` points to this folder.
*   **Python:**
    *   Nodes are implemented as classes that inherit from base ComfyUI classes or custom base classes.
    *   They define `INPUT_TYPES`, `RETURN_TYPES`, `FUNCTION`, and `CATEGORY` class attributes, which is standard for ComfyUI custom nodes.
*   **JavaScript:**
    *   The JavaScript code uses a class-based system.
    *   `HolafBaseNode` and its subclasses provide a structured way to create custom nodes and widgets.
    *   The code overrides the default ComfyUI node registration to inject the custom JavaScript classes for the corresponding Python nodes.
