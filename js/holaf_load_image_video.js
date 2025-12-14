import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "Holaf.LoadImageVideo",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "HolafLoadImageVideo") {
            
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);

                const node = this;
                const widget = node.widgets.find(w => w.name === "media_file");
                
                // 1. Conteneur principal qui gère la disposition verticale
                const mainContainer = document.createElement("div");
                Object.assign(mainContainer.style, {
                    width: "100%",
                    display: "flex",
                    flexDirection: "column",
                    gap: "5px" // Espace entre le preview et le bouton
                });

                // 2. Le conteneur du preview (comme avant)
                const previewContainer = document.createElement("div");
                Object.assign(previewContainer.style, {
                    width: "100%",
                    height: "200px",
                    backgroundColor: "rgba(0,0,0,0.2)",
                    borderRadius: "4px",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    overflow: "hidden"
                });

                // 3. Le bouton, maintenant en HTML, plus en widget canvas
                const uploadButton = document.createElement("button");
                uploadButton.textContent = "📤 Upload Image/Video";
                Object.assign(uploadButton.style, {
                    width: "100%",
                    padding: "5px",
                    fontSize: "inherit", // S'adapte au style de Comfy
                    backgroundColor: "#333",
                    color: "#fff",
                    border: "1px solid #555",
                    borderRadius: "4px",
                    cursor: "pointer"
                });

                // On assemble la structure : Preview en haut, Bouton en bas
                mainContainer.appendChild(previewContainer);
                mainContainer.appendChild(uploadButton);

                // On injecte le tout dans UN SEUL widget DOM
                node.addDOMWidget("holaf_media_loader", "div", mainContainer, {
                    serialize: false,
                    hideOnZoom: false
                });
                
                // Le redimensionnement s'applique toujours au conteneur du preview
                node.onResize = function(size) {
                    const buttonHeight = uploadButton.offsetHeight + 5; // Hauteur bouton + gap
                    const widgetsHeight = node.widgets.length * 22; // Approximation
                    const freeHeight = Math.max(50, size[1] - widgetsHeight - buttonHeight); 
                    previewContainer.style.height = freeHeight + "px";
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

                    Object.assign(el.style, { width: "100%", height: "100%", objectFit: "contain", display: "block" });
                    previewContainer.appendChild(el);
                };

                // --- Logique d'upload (maintenant liée au bouton HTML) ---
                const fileInput = document.createElement("input");
                Object.assign(fileInput, { type: "file", accept: "image/*,video/*,.mkv,.avi,.mov", style: "display:none" });
                document.body.appendChild(fileInput);

                uploadButton.onclick = () => { fileInput.click(); }; // Le clic sur le bouton HTML déclenche l'input caché

                fileInput.onchange = async () => {
                    if (!fileInput.files.length) return;
                    const file = fileInput.files[0];
                    const formData = new FormData();
                    formData.append("image", file);
                    formData.append("overwrite", "true");

                    try {
                        uploadButton.textContent = "⏳ Uploading...";
                        const resp = await api.fetchApi("/upload/image", { method: "POST", body: formData });
                        if (resp.status === 200) {
                            const data = await resp.json();
                            if (widget) {
                                if (!widget.options.values.includes(data.name)) widget.options.values.push(data.name);
                                widget.value = data.name;
                                widget.callback(data.name);
                            }
                        } else { alert(`Upload failed: ${resp.status}`); }
                    } catch (err) { alert(`Error: ${err.message}`); } 
                    finally { uploadButton.textContent = "📤 Upload Image/Video"; fileInput.value = ""; }
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