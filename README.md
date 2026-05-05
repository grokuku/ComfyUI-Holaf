# Holaf Custom Nodes for ComfyUI

This repository contains a collection of custom nodes for ComfyUI.

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

### Image Processing & UI
*   **Image Comparer (Holaf)**
    *   *Function:* Interactive side-by-side comparison with "Slide" or "Click" modes.
*   **Image Adjustment (Holaf)**
    *   *Function:* Brightness, Contrast, and Saturation adjustments (pure PyTorch).
*   **Image Batch Slice (Holaf)**
    *   *Function:* Slices a batch of images into smaller batches.
*   **Instagram Resize (Holaf)**
    *   *Function:* Resizes an image to standard Instagram aspect ratios (1:1, 4:5, 16:9) by adding padding.
*   **Overlay (Holaf)**
    *   *Function:* Overlays an image onto a background with size, position, opacity, and masking controls.
*   **Upscale (Holaf)**
    *   *Function:* Upscales an image to a target megapixel count using a specified model.
    *   *Dependencies:* `spandrel`.

### Media I/O
*   **Save Media (Holaf)**
    *   *Function:* Unified saver for Images, Videos, and Audio. Supports NVENC GPU encoding, temp file encoding for fast I/O, timed subfolder/file naming, and separate prompt/workflow export.
    *   *Dependencies:* `av` (PyAV).
*   **Load Image/Video (Holaf)**
    *   *Function:* Unified loader for images and videos (MP4, GIF, etc.) with custom preview widget.
    *   *Dependencies:* `av` (PyAV).
*   **Video Preview (Holaf)**
    *   *Function:* Previews video output directly in the ComfyUI UI.

### Calculators & Utilities
*   **Resolution Preset (Holaf)**
    *   *Function:* Selects optimal image dimensions based on a target model (SD1.5, SDXL, FLUX, Qwen, Z-Image) and aspect ratio.
*   **Text Box (Holaf)**
    *   *Function:* Simple text box with optional input for concatenation.
*   **To Text (Holaf)**
    *   *Function:* Debug node that converts any input to a formatted string (Markdown, JSON, Tensor info).

### Masking
*   **Mask to Boolean (Holaf)**
    *   *Function:* Checks if a mask is empty (all black) and outputs a boolean for conditional bypass logic.

### Sampling
*   **KSampler (Holaf)**
    *   *Function:* KSampler with direct image input (auto-encoding), VRAM clearing, and conditional bypass.
*   **Tiled KSampler (Holaf)**
    *   *Function:* Tiled sampling with cosine feathered blending and tiled VAE encode/decode. Designed for high-resolution generation.

### Flow Control & Logic
*   **Bypasser (Holaf)**
    *   *Function:* Toggle switch (Always/Bypass) for conditional graph execution.
*   **Group Bypasser (Holaf)**
    *   *Function:* Bypasser that can mute/bypass entire ComfyUI groups.
*   **Remote (Holaf)**
    *   *Function:* Remote control output to pilot Bypassers of the same group.
*   **Remote Selector (Holaf)**
    *   *Function:* Radio-button style remote — activates one group among a user-defined list, deactivating all others.
*   **Auto Select x2 (Holaf)**
    *   *Function:* Selects the first active input between two (Priority 1 > 2).
*   **Bundle Creator (Holaf)**
    *   *Function:* Groups up to 20 varied inputs into a single bundle.
*   **Bundle Extractor (Holaf)**
    *   *Function:* Extracts data from a bundle back to 20 corresponding outputs.

### LUT (Look-Up Table) Tools
*   **LUT Generator (Holaf)**
    *   *Function:* Analyzes the color profile of a reference image and generates a 3D LUT.
*   **LUT Saver (Holaf)**
    *   *Function:* Saves a generated LUT to a `.cube` file.

### Experimental (Optional Dependencies)
*   **Nucleus-Image (Holaf)**
    *   *Function:* MoE-based image pipeline. Requires `diffusers >= 0.38`.