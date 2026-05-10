import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// ── Upload helper (used both by file input and clipboard paste) ──
async function uploadFileAndSetWidget(node, file, uploadButton) {
    const widget = node.widgets.find(w => w.name === "media_file");
    if (!widget) return;
    const formData = new FormData();
    formData.append("image", file);
    formData.append("overwrite", "true");
    try {
        if (uploadButton) uploadButton.textContent = "⏳ Uploading...";
        const resp = await api.fetchApi("/upload/image", { method: "POST", body: formData });
        if (resp.status === 200) {
            const data = await resp.json();
            if (!widget.options.values.includes(data.name)) widget.options.values.push(data.name);
            widget.value = data.name;
            widget.callback?.(data.name);
        } else {
            alert(`Upload failed: ${resp.status}`);
        }
    } catch (err) {
        alert(`Error: ${err.message}`);
    } finally {
        if (uploadButton) uploadButton.textContent = "📤 Upload Image/Video";
    }
}

app.registerExtension({
    name: "Holaf.LoadImageVideo",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "HolafLoadImageVideo") {

            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);

                const node = this;
                const widget = node.widgets.find(w => w.name === "media_file");
                
                // 1. Conteneur principal — pointer-events: none pour que le clic droit
                //    (menu contextuel standard de ComfyUI) traverse vers le canvas.
                const mainContainer = document.createElement("div");
                Object.assign(mainContainer.style, {
                    width: "100%",
                    display: "flex",
                    flexDirection: "column",
                    gap: "5px",
                    pointerEvents: "none"
                });

                // 2. Le conteneur du preview — flex:1 + pointer-events:none
                //    pour que le clic droit traverse jusqu'au canvas LiteGraph.
                const previewContainer = document.createElement("div");
                Object.assign(previewContainer.style, {
                    width: "100%",
                    flex: "1 1 auto",
                    minHeight: "50px",
                    backgroundColor: "rgba(0,0,0,0.2)",
                    borderRadius: "4px",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    overflow: "hidden",
                    pointerEvents: "none"
                });

                // 3. Le bouton — pointer-events: auto pour rester cliquable
                const uploadButton = document.createElement("button");
                uploadButton.textContent = "📤 Upload Image/Video";
                Object.assign(uploadButton.style, {
                    width: "100%",
                    padding: "5px",
                    fontSize: "inherit",
                    backgroundColor: "#333",
                    color: "#fff",
                    border: "1px solid #555",
                    borderRadius: "4px",
                    cursor: "pointer",
                    pointerEvents: "auto"
                });

                // On assemble la structure : Preview en haut, Bouton en bas
                mainContainer.appendChild(previewContainer);
                mainContainer.appendChild(uploadButton);

                // On injecte le tout dans UN SEUL widget DOM
                const domWidgetIdx = node.addDOMWidget("holaf_media_loader", "div", mainContainer, {
                    serialize: false,
                    hideOnZoom: false
                });
                const domWidget = (typeof domWidgetIdx === 'number')
                    ? node.widgets[domWidgetIdx]
                    : node.widgets.find(w => w.name === "holaf_media_loader");

                // Le conteneur DOM doit suivre la taille du nœud.
                // On utilise last_y du DOM widget (position calculée par ComfyUI lors
                // du layout) pour déterminer l'espace disponible.
                const origOnResize = node.onResize;
                node.onResize = function(size) {
                    if (origOnResize) origOnResize.apply(this, arguments);
                    // Hauteur dispo = hauteur du nœud − position Y du widget − marge basse
                    const titleBar = LiteGraph.NODE_TITLE_HEIGHT || 24;
                    const top = (domWidget && domWidget.last_y > 0) ? domWidget.last_y : titleBar + 40;
                    const freeHeight = Math.max(50, size[1] - top - 8);
                    mainContainer.style.height = freeHeight + "px";
                };

                const updatePreview = (filename) => {
                    previewContainer.innerHTML = "";
                    if (!filename) {
                        previewContainer.textContent = "No Media";
                        return;
                    }

                    const url = api.apiURL(`/view?filename=${encodeURIComponent(filename)}&type=input`);
                    const ext = filename.split('.').pop().toLowerCase();
                    const isVideo = ['mp4', 'webm', 'mov', 'avi', 'mkv', 'm4v'].includes(ext);

                    let el;
                    if (isVideo) { el = document.createElement("video"); el.autoplay = true; el.muted = true; el.loop = true; el.controls = true; } 
                    else { el = document.createElement("img"); }
                    el.src = url;

                    Object.assign(el.style, { width: "100%", height: "100%", objectFit: "contain", display: "block", pointerEvents: "none" });
                    previewContainer.appendChild(el);
                };

                // --- Upload via file input (bouton HTML) ---
                const fileInputId = 'holaf_file_input_' + node.id;
                document.querySelectorAll('input.holaf_file_input[data-node-id="' + node.id + '"]')
                    .forEach(el => el.remove());
                const oldFileInput = document.getElementById(fileInputId);
                if (oldFileInput) oldFileInput.remove();
                const fileInput = document.createElement("input");
                fileInput.id = fileInputId;
                fileInput.className = 'holaf_file_input';
                fileInput.dataset.nodeId = node.id;
                Object.assign(fileInput, { type: "file", accept: "image/*,video/*,.mkv,.avi,.mov", style: "display:none" });
                document.body.appendChild(fileInput);

                uploadButton.onclick = () => { fileInput.click(); };

                fileInput.onchange = async () => {
                    if (!fileInput.files.length) return;
                    await uploadFileAndSetWidget(node, fileInput.files[0], uploadButton);
                    fileInput.value = "";
                };

                // --- Reste de la logique (inchangée) ---
                if (widget) {
                    const originalCallback = widget.callback;
                    widget.callback = function(v) { if (originalCallback) originalCallback(v); updatePreview(v); };
                    setTimeout(() => { if (widget.value) updatePreview(widget.value); }, 100);
                }
                const onRemoved = node.onRemoved;
                node.onRemoved = function() { if (onRemoved) onRemoved.apply(this, arguments); fileInput.remove(); };
            };

            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(message) {
                if (onExecuted) onExecuted.apply(this, arguments);
                if (message?.images?.length) {
                    const filename = message.images[0].filename;
                    const widget = this.widgets.find(w => w.name === "media_file");
                    if (widget && widget.value !== filename) {
                        widget.value = filename;
                        if(widget.callback) widget.callback(filename);
                    }
                }
            };


        }
    }
});