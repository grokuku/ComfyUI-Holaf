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
                    width: "90%", // On laisse 5% de marge de chaque côté
                    marginLeft: "5%",
                    height: "100%",
                    backgroundColor: "#222",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    borderRadius: "5px",
                    overflow: "hidden", // Coupe tout ce qui dépasse
                    border: "1px solid #333",
                    boxSizing: "border-box" // Important pour les calculs de taille
                });

                // Message par défaut
                const placeholder = document.createElement("span");
                placeholder.textContent = "🎬 Preview Ready";
                placeholder.style.color = "#666";
                placeholder.style.fontSize = "12px";
                container.appendChild(placeholder);

                // Ajout au nœud via un widget DOM
                node.addDOMWidget("video_player", "div", container, {
                    serialize: false,
                    hideOnZoom: false
                });

                node.videoContainer = container;
            };

            // --- Gestion de la taille du widget (Le correctif est ici) ---
            const onResize = nodeType.prototype.onResize;
            nodeType.prototype.onResize = function (size) {
                if (onResize) onResize.apply(this, arguments);

                // 1. Calcul de l'espace occupé par les autres widgets (fps, quality, etc.)
                // On compte environ 30px par widget standard + 40px pour l'entête du nœud
                let usedHeight = 40;
                if (this.widgets) {
                    // On ne compte pas le widget vidéo lui-même
                    const otherWidgets = this.widgets.filter(w => w.name !== "video_player");
                    usedHeight += otherWidgets.length * 30;
                }

                // 2. On ajoute une marge de sécurité en bas (20px)
                usedHeight += 20;

                // 3. Calcul de la hauteur disponible
                const freeHeight = Math.max(50, size[1] - usedHeight);

                if (this.videoContainer) {
                    this.videoContainer.style.height = freeHeight + "px";
                }
            };

            // --- Réception des données Python ---
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                if (onExecuted) onExecuted.apply(this, arguments);

                if (message?.holaf_video && message.holaf_video.length > 0) {
                    const videoData = message.holaf_video[0];
                    const node = this;

                    if (node.videoContainer) {
                        node.videoContainer.innerHTML = "";

                        const videoEl = document.createElement("video");

                        const params = new URLSearchParams({
                            filename: videoData.filename,
                            subfolder: videoData.subfolder,
                            type: videoData.type
                        });

                        videoEl.src = api.apiURL(`/view?${params.toString()}&t=${Date.now()}`);

                        videoEl.controls = true;
                        videoEl.autoplay = true;
                        videoEl.muted = true;
                        videoEl.loop = true;

                        Object.assign(videoEl.style, {
                            width: "100%",
                            height: "100%",
                            objectFit: "contain" // L'image ne sera jamais déformée ni coupée
                        });

                        node.videoContainer.appendChild(videoEl);
                    }
                }
            };
        }
    }
});