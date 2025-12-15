import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "Holaf.VideoPreview",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "HolafVideoPreview") {

            // --- Création du Widget Vidéo ---
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);

                const node = this;

                // Création de l'élément DOM container
                const container = document.createElement("div");
                Object.assign(container.style, {
                    width: "100%",
                    height: "100%",
                    backgroundColor: "#222",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    borderRadius: "5px",
                    overflow: "hidden",
                    border: "1px solid #333"
                });

                // Message par défaut
                const placeholder = document.createElement("span");
                placeholder.textContent = "🎬 Preview Ready";
                placeholder.style.color = "#666";
                placeholder.style.fontSize = "12px";
                container.appendChild(placeholder);

                // Ajout au nœud via un widget DOM
                // On met une hauteur par défaut généreuse pour bien voir la vidéo
                node.addDOMWidget("video_player", "div", container, {
                    serialize: false,
                    hideOnZoom: false
                });

                // On stocke la référence pour l'update
                node.videoContainer = container;
            };

            // --- Gestion de la taille du widget ---
            const onResize = nodeType.prototype.onResize;
            nodeType.prototype.onResize = function (size) {
                if (onResize) onResize.apply(this, arguments);

                // Ajuster la hauteur du container vidéo
                // On soustrait la hauteur des inputs (~40px pour fps/quality)
                const headerHeight = 50;
                const newHeight = Math.max(100, size[1] - headerHeight);

                if (this.videoContainer) {
                    this.videoContainer.style.height = newHeight + "px";
                }
            };

            // --- Réception des données Python ---
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                if (onExecuted) onExecuted.apply(this, arguments);

                // On cherche notre clé spécifique "holaf_video"
                if (message?.holaf_video && message.holaf_video.length > 0) {
                    const videoData = message.holaf_video[0];
                    const node = this;

                    if (node.videoContainer) {
                        node.videoContainer.innerHTML = ""; // Clear placeholder

                        const videoEl = document.createElement("video");

                        // URL vers le fichier temporaire
                        const params = new URLSearchParams({
                            filename: videoData.filename,
                            subfolder: videoData.subfolder,
                            type: videoData.type
                        });

                        // Timestamp pour éviter le cache
                        videoEl.src = api.apiURL(`/view?${params.toString()}&t=${Date.now()}`);

                        // Options du lecteur
                        videoEl.controls = true;
                        videoEl.autoplay = true;
                        videoEl.muted = true; // Nécessaire pour l'autoplay
                        videoEl.loop = true;

                        Object.assign(videoEl.style, {
                            width: "100%",
                            height: "100%",
                            objectFit: "contain"
                        });

                        node.videoContainer.appendChild(videoEl);
                    }
                }
            };
        }
    }
});