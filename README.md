# Holaf Custom Nodes for ComfyUI

This repository contains a collection of experimental custom nodes for ComfyUI.

---

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## ⚠️ WARNING: Experimental & No Support ⚠️

**Please be aware:**

*   These nodes are experimental and provided **AS IS**.
*   They may contain bugs, instabilities, or change significantly without notice.
*   **NO SUPPORT IS PROVIDED** for these nodes. Use them at your own risk.
*   Compatibility with future versions of ComfyUI is not guaranteed.

---

## Installation

1.  Clone this repository into your `ComfyUI/custom_nodes/` directory.
2.  Install required dependencies by running the following command in your ComfyUI's Python environment:
    ```bash
    pip install -r requirements.txt
    ```
3.  Restart ComfyUI.

---

## Available Nodes

Here is a list of the custom nodes included in this package:

### Image Processing & UI
*   **Image Comparer (Holaf)**
    *   *Function:* An interactive node to compare two images side-by-side with "Slide" or "Click" modes directly in the UI.
*   **Instagram Resize (Holaf)**
    *   *Function:* Resizes an image to the closest standard Instagram aspect ratio (1:1, 4:5, 16:9) by adding colored bars (padding) instead of cropping.
*   **Overlay (Holaf)**
    *   *Function:* Overlays an 'overlay_image' onto a 'background_image' with controls for size, position, opacity, and masking.
*   **Upscale (Holaf)**
    *   *Function:* Upscales an input image to a target megapixel count using a specified upscaling model.
    *   *Dependencies:* `spandrel`.

### Calculators & Utilities
*   **Resolution Preset (Holaf)**
    *   *Function:* Helps select optimal image dimensions (width, height) based on a target model (SD1.5, SDXL, FLUX) and a desired aspect ratio.

### Masking
*   **Mask to Boolean (Holaf)**
    *   *Function:* Checks if a mask is empty (all black) and outputs a boolean value. Ideal for creating conditional bypass logic in workflows.

### Sampling
*   **KSampler (Holaf)**
    *   *Function:* A KSampler implementation with added support for direct image input (auto-encoding), VRAM clearing, and a conditional bypass.
*   **Tiled KSampler (Holaf)**
    *   *Function:* Implements the KSampler algorithm specifically designed to work on image tiles, useful for high-resolution generation.

### LUT (Look-Up Table) Tools
*   **LUT Generator (Holaf)**
    *   *Function:* Analyzes the color profile of a reference image and generates a 3D Look-Up Table (LUT).
*   **LUT Saver (Holaf)**
    *   *Function:* Saves a generated LUT to a `.cube` file.

### Workflow
*   **Save Image (Holaf)**
    *   *Function:* Provides advanced options for saving images, with separate `.json` and `.txt` files for the workflow and prompt.