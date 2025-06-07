# Holaf Custom Nodes for ComfyUI

This repository contains a collection of experimental custom nodes for ComfyUI.

*Note: These nodes were developed with AI assistance using Visual Studio Code and Cline.*

---

## ⚠️ WARNING: Experimental & No Support ⚠️

**Please be aware:**

*   These nodes are experimental and provided **AS IS**.
*   They may contain bugs, instabilities, or change significantly without notice.
*   **NO SUPPORT IS PROVIDED** for these nodes. Use them at your own risk.
*   Compatibility with future versions of ComfyUI is not guaranteed.

---

## Available Nodes

Here is a list of the custom nodes included in this package:

*   **Benchmark Loader (Holaf)**
    *   *Function:* Loads selected SD checkpoints or FLUX UNets and outputs information for the Benchmark Runner.
*   **Benchmark Plotter (Holaf)**
    *   *Function:* Reads benchmark CSV data (from Benchmark Runner) and generates plots (light/dark themes) showing Pixels/Second vs Resolution. Requires `pandas` and `matplotlib`.
*   **Benchmark Runner (Holaf)**
    *   *Function:* Runs KSampler benchmarks on selected SD models across different resolutions. Outputs results as a CSV string. (FLUX benchmarking currently unsupported). Optionally requires `psutil` for full system info.
*   **Color Matcher (Holaf)**
    *   *Function:* Transfers color characteristics (luminance, contrast, saturation, and overall color balance) from a reference image to a source image, with mix controls for each effect.
*   **Image Comparer (Holaf)**
    *   *Function:* Allows comparing two images side-by-side within the ComfyUI interface. Requires associated JavaScript file.
*   **Instagram Resize (Holaf)**
    *   *Function:* Resizes an image to the closest standard Instagram aspect ratio (1:1, 4:5, 16:9) by adding colored bars (padding) instead of cropping.
*   **KSampler (Holaf)**
    *   *Function:* A KSampler implementation, with minor modifications.
*   **Neurogrid Overload (Holaf)**
    *   *Function:* Tetris clone that will kill your framerate or crash. (Avoid keeping it in a workflow). Requires associated JavaScript file.
*   **Overlay (Holaf)**
    *   *Function:* Overlays an 'overlay_image' onto a 'background_image' with controls for size, position, opacity, and masking.
*   **Resolution Preset (Holaf)**
    *   *Function:* Helps select optimal image dimensions (width, height) based on a target model (SD1.5, SDXL, FLUX) and a desired aspect ratio (dropdown or from input image).
*   **Save Image (Holaf)**
    *   *Function:* Provides options for saving images, with separate json and txt files for workflow and prompt.
*   **Slice Calculator (Holaf)**
    *   *Function:* Similar to the Tile Calculator, calculates parameters for slicing images.
*   **Tile Calculator (Holaf)**
    *   *Function:* Calculates parameters needed for processing images in tiles (e.g., dimensions, overlap).
*   **Tiled KSampler (Holaf)**
    *   *Function:* Implements the KSampler algorithm specifically designed to work on image tiles, useful for high-resolution generation.
*   **Upscale (Holaf)**
    *   *Function:* Upscales an input image to a target megapixel count using a specified model or method.

---

## Installation

1.  Clone this repository into your `ComfyUI/custom_nodes/` directory.
2.  Restart ComfyUI.