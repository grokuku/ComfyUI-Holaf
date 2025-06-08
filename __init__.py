# === Documentation ===
# Author: Cline (AI Assistant)
# Date: 2025-04-01
#
# Purpose:
# This __init__.py file serves as the main entry point for the 'ComfyUI-Holaf'
# custom node package. It is responsible for making the custom nodes defined
# within this package discoverable and usable by the ComfyUI application.
#
# Design Choices & Rationale:
# - Centralized Registration: Follows the standard ComfyUI pattern for custom
#   node packages. ComfyUI looks for this file to understand what nodes the
#   package provides.
# - Modular Imports: Imports individual node classes (e.g., HolafTileCalculator,
#   HolafSaveImage) from their respective files within the `./nodes/` subdirectory.
#   This keeps the node implementations organized in separate files.
# - NODE_CLASS_MAPPINGS: This dictionary is crucial for ComfyUI. It maps a unique
#   internal string identifier (typically the class name) for each node to the
#   actual Python class that implements the node's logic. ComfyUI uses this map
#   to instantiate the correct node object when loading or running a workflow.
# - NODE_DISPLAY_NAME_MAPPINGS: This dictionary maps the same internal string
#   identifiers to user-friendly names that appear in the ComfyUI "Add Node" menu.
#   This allows for more readable or descriptive names than the raw class names.
# - WEB_DIRECTORY: Specifies the relative path to the directory containing
#   associated web assets (JavaScript files in this case) needed for the frontend
#   components of certain custom nodes (like HolafImageComparer). ComfyUI serves
#   files from this directory.
# - __all__ Export: Explicitly lists the mapping dictionaries (`NODE_CLASS_MAPPINGS`,
#   `NODE_DISPLAY_NAME_MAPPINGS`, `WEB_DIRECTORY`) to be exported when the package is imported.
#   This is standard Python practice and ensures ComfyUI can access these essential variables.
# - Initialization Feedback: Includes a print statement to the console upon successful
#   loading, providing visual confirmation that the custom node package has been
#   recognized and initialized by ComfyUI.
# === End Documentation ===

# --- MODIFICATION : Import de 'server' et 'os' pour le chargement du JS ---
import server
import os
import sys
import hashlib
# --- FIN MODIFICATION ---


# Import classes from the nodes directory
from .nodes.holaf_neurogrid_overload import HolafNeurogridOverload
from .nodes.holaf_tile_calculator import HolafTileCalculator
from .nodes.holaf_slice_calculator import HolafSliceCalculator
from .nodes.holaf_save_image import HolafSaveImage
from .nodes.holaf_tiled_ksampler import HolafTiledKSampler
from .nodes.holaf_ksampler import HolafKSampler
from .nodes.holaf_image_comparer import HolafImageComparer
from .nodes.holaf_upscale_image import UpscaleImageHolaf
from .nodes.holaf_overlay import HolafOverlayNode
from .nodes.holaf_resolution_preset import HolafResolutionPreset
from .nodes.HolafBenchmarkRunner import HolafBenchmarkRunner
from .nodes.HolafBenchmarkPlotter import HolafBenchmarkPlotter
from .nodes.HolafBenchmarkLoader import HolafBenchmarkLoader
from .nodes.holaf_instagram_resize import HolafInstagramResize
from .nodes.holaf_color_matcher import HolafColorMatcher
from .nodes.holaf_lut_generator import HolafLutGenerator
from .nodes.holaf_lut_applier import HolafLutApplier
from .nodes.holaf_lut_loader import HolafLutLoader
from .nodes.holaf_lut_saver import HolafLutSaver
# --- MODIFICATION : Import de la nouvelle node interactive_image_editor ---
from .nodes.holaf_interactive_image_editor import HolafInteractiveImageEditor
# --- FIN MODIFICATION ---


# Define node mappings for ComfyUI
NODE_CLASS_MAPPINGS = {
    "HolafNeurogridOverload": HolafNeurogridOverload,
    "HolafTileCalculator": HolafTileCalculator,
    "HolafSliceCalculator": HolafSliceCalculator,
    "HolafSaveImage": HolafSaveImage,
    "HolafTiledKSampler": HolafTiledKSampler,
    "HolafKSampler": HolafKSampler,
    'HolafImageComparer': HolafImageComparer,
    "UpscaleImageHolaf": UpscaleImageHolaf,
    "HolafOverlayNode": HolafOverlayNode,
    "HolafResolutionPreset": HolafResolutionPreset,
    "HolafBenchmarkRunner": HolafBenchmarkRunner,
    "HolafBenchmarkPlotter": HolafBenchmarkPlotter,
    "HolafBenchmarkLoader": HolafBenchmarkLoader,
    "HolafInstagramResize": HolafInstagramResize,
    "HolafColorMatcher": HolafColorMatcher,
    "HolafLutGenerator": HolafLutGenerator,
    "HolafLutApplier": HolafLutApplier,
    "HolafLutLoader": HolafLutLoader,
    "HolafLutSaver": HolafLutSaver,
    # --- MODIFICATION : Ajout du mapping pour la nouvelle node ---
    "HolafInteractiveImageEditor": HolafInteractiveImageEditor,
    # --- FIN MODIFICATION ---
}

# Define display name mappings
NODE_DISPLAY_NAME_MAPPINGS = {
    "HolafNeurogridOverload": "Neurogrid Overload (Holaf)",
    "HolafTileCalculator": "Tile Calculator (Holaf)",
    "HolafSliceCalculator": "Slice Calculator (Holaf)",
    "HolafSaveImage": "Save Image (Holaf)",
    "HolafTiledKSampler": "Tiled KSampler (Holaf)",
    "HolafKSampler": "KSampler (Holaf)",
    'HolafImageComparer': "Image Comparer (Holaf)",
    "UpscaleImageHolaf": "Upscale (Holaf)",
    "HolafOverlayNode": "Overlay (Holaf)",
    "HolafResolutionPreset": "Resolution Preset (Holaf)",
    "HolafBenchmarkRunner": "Benchmark Runner (Holaf)",
    "HolafBenchmarkPlotter": "Benchmark Plotter (Holaf)",
    "HolafBenchmarkLoader": "Benchmark Loader (Holaf)",
    "HolafInstagramResize": "Instagram Resize (Holaf)",
    "HolafColorMatcher": "Color Matcher (Holaf)",
    "HolafLutGenerator": "LUT Generator (Holaf)",
    "HolafLutApplier": "LUT Applier (Holaf)",
    "HolafLutLoader": "LUT Loader (Holaf)",
    "HolafLutSaver": "LUT Saver (Holaf)",
    # --- MODIFICATION : Ajout du nom d'affichage pour la nouvelle node ---
    "HolafInteractiveImageEditor": "Interactive Image Editor (Holaf)",
    # --- FIN MODIFICATION ---
}

# --- MODIFICATION : Chargement dynamique et versionné des fichiers JS ---

# Obtenez le chemin absolu du dossier 'js' de ce custom node
js_web_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "js")
# Rendez le dossier 'js' accessible au serveur web de ComfyUI
server.PromptServer.instance.add_extra_path("holaf", js_web_path)

# Liste des fichiers JS que nous voulons charger
javascript_files = [
    "holaf_image_comparer.js",
    "holaf_interactive_editor.js",
    "holaf_lut_loader.js",
    "holaf_neurogrid_overload.js"
]

# Calcule un hash de tous les fichiers JS pour forcer le rechargement si l'un d'eux change
m = hashlib.sha256()
for js_file in javascript_files:
    js_path = os.path.join(js_web_path, js_file)
    if os.path.exists(js_path):
        with open(js_path, 'rb') as f:
            m.update(f.read())

version_hash = m.hexdigest()[:8] # Un hash court pour la version

# Enregistre chaque fichier JS avec le paramètre de version
for js_file in javascript_files:
     # La route pour le navigateur sera /holaf/nom_du_fichier.js?v=hash
    server.PromptServer.instance.add_js_file(f"/holaf/{js_file}?v={version_hash}", __name__)

# La variable WEB_DIRECTORY n'est plus nécessaire avec cette méthode
WEB_DIRECTORY = "./js" # Gardons la pour la compatibilité, mais la méthode ci-dessus est prioritaire

# --- FIN MODIFICATION ---

# Indicate successful loading
print("✅ Holaf Custom Nodes initialized")

# Export mappings for ComfyUI
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']