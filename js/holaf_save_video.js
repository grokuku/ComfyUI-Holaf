import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "Holaf.SaveVideo",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "HolafSaveVideo") {

            // 1. À la création du nœud, on ajoute le widget de preview
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);

                const node = this;

                // Création du conteneur HTML pour la vidéo
                const widget = {
                    type: "div",
                    name: "video_preview",
                    draw(ctx, node, widget_width, y, widget_height) {
                        // On force le positionnement pour qu'il s'aligne bien dans le nœud
                        Object.assign(this.div.style, {
                            width: "100%",
                            height: "100%",
                            position: "absolute",
                            left: "0",
                            top: y + "px",
                        });
                    },
                    div: document.createElement("div"),
                };

                // Style par défaut (gris, centré)
                Object.assign(widget.div.style, {
                    width: "100%",
                    height: "200px", // Hauteur initiale
                    backgroundColor: "rgba(0,0,0,0.2)",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    borderRadius: "4px",
                    overflow: "hidden",
                    color: "#aaa",
                    fontSize: "12px",
                    fontFamily: "sans-serif"
                });

                widget.div.textContent = "Waiting for generation...";

                // Ajout au DOM du nœud
                node.addDOMWidget("video_preview", "div", widget.div, {
                    serialize: false,
                    hideOnZoom: false
                });

                // Gestion du redimensionnement du nœud
                node.onResize = function (size) {
                    // Calcul de la place prise par les autres inputs pour donner le reste à la vidéo
                    const inputsHeight = (node.inputs ? node.inputs.length * 20 : 0) +
                        (node.widgets ? node.widgets.filter(w => w.type !== "div").length * 22 : 0) + 40;

                    const freeHeight = Math.max(100, size[1] - inputsHeight);
                    widget.div.style.height = freeHeight + "px";
                };
            };

            // 2. À la fin de l'exécution, on récupère le fichier et on l'affiche
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                if (onExecuted) onExecuted.apply(this, arguments);

                // Votre code Python renvoie des clés comme "mp4s", "gifs", etc.
                let fileInfo = null;
                const supportedKeys = ["mp4s", "webms", "gifs"];

                for (const key of supportedKeys) {
                    if (message[key] && message[key].length > 0) {
                        fileInfo = message[key][0];
                        break;
                    }
                }

                if (fileInfo) {
                    const node = this;
                    const widget = node.widgets.find(w => w.name === "video_preview");

                    if (widget && widget.div) {
                        widget.div.innerHTML = ""; // Nettoyage

                        // Construction de l'URL pour récupérer la vidéo via l'API ComfyUI
                        const params = new URLSearchParams({
                            filename: fileInfo.filename,
                            subfolder: fileInfo.subfolder,
                            type: fileInfo.type,
                            format: fileInfo.format
                        });

                        // astuce: on ajoute un timestamp pour forcer le rafraichissement si on ré-exécute
                        const url = api.apiURL(`/view?${params.toString()}&t=${Date.now()}`);

                        let el;
                        if (fileInfo.format === 'gif') {
                            el = document.createElement("img");
                        } else {
                            el = document.createElement("video");
                            el.autoplay = true;
                            el.muted = true; // Chrome bloque l'autoplay si le son est activé
                            el.loop = true;
                            el.controls = true;
                        }

                        el.src = url;
                        Object.assign(el.style, {
                            width: "100%",
                            height: "100%",
                            objectFit: "contain" // Garde les proportions
                        });

                        widget.div.appendChild(el);
                    }
                }
            };
        }
    }
});