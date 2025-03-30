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

*   **Neurogrid Overload (Holaf)**
    *   *Function:* Tetris clone that will kill your frame or crash. (avoid keeping it in a workflow)
*   **Tile Calculator (Holaf)**
    *   *Function:* Calculates parameters needed for processing images in tiles (e.g., dimensions, overlap).
*   **Slice Calculator (Holaf)**
    *   *Function:* Similar to the Tile Calculator, calculates parameters for slicing images.
*   **Save Image (Holaf)**
    *   *Function:* Provides options for saving images, with separate json and txt files for workflow and prompt.
*   **Tiled KSampler (Holaf)**
    *   *Function:* Implements the KSampler algorithm specifically designed to work on image tiles, useful for high-resolution generation.
*   **KSampler (Holaf)**
    *   *Function:* A KSampler implementation, with minor modifications.
*   **Image Comparer (Holaf)**
    *   *Function:* Allows comparing two images side-by-side within the ComfyUI interface.
*   **Upscale (Holaf)**
    *   *Function:* Upscales an input image to a MP count using a specified model or method.

---

## Installation

1.  Clone this repository into your `ComfyUI/custom_nodes/` directory.
2.  Restart ComfyUI.
