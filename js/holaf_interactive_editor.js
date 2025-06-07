import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

function getImageDataAsUrl(image_data) {
    if (!image_data || !image_data.filename || typeof image_data.filename !== 'string') { return null; }
    const url = api.apiURL(`/view?filename=${encodeURIComponent(image_data.filename)}&type=${encodeURIComponent(image_data.type || 'output')}&subfolder=${encodeURIComponent(image_data.subfolder || '')}${app.getPreviewFormatParam()}${app.getRandParam()}`);
    return url;
}

const HolafInteractiveEditorNodeType = "HolafInteractiveImageEditor";

app.registerExtension({
    name: "Holaf.InteractiveImageEditor.V15_DebugSizing_Full", // Updated version name
    async beforeRegisterNodeDef(nodeType, nodeData, appInstance) {
        if (nodeData.name === HolafInteractiveEditorNodeType) {

            nodeType.prototype.onDrawForeground = function(ctx, graphCanvas) { /* Vide car géré par le widget DOM */ };

            nodeType.prototype.onNodeCreated = function () {
                // console.log(`[Holaf Editor DEBUG] onNodeCreated called for node ${this.id}`);
                this.imageOriginal = new Image();
                this.imageModified = new Image();
                this.imagesLoaded = { original: false, modified: false };
                this.separatorXRatio = 0.5;
                this.isMouseOverImageCanvas = false;
                this.lastMessage = null; // Stocke le dernier message UI reçu

                // Conteneur principal pour le canvas et le bouton
                this.domContainer = document.createElement("div");
                this.domContainer.className = "holaf-editor-dom-container";
                this.domContainer.style.width = "100%"; // Prendra la largeur du widget allouée par LiteGraph
                this.domContainer.style.display = "flex";
                this.domContainer.style.flexDirection = "column"; // Empiler canvas et bouton
                this.domContainer.style.minHeight = "50px"; // Pour éviter qu'il ne s'effondre complètement

                // Canvas pour l'image
                this.imageCanvasElement = document.createElement("canvas");
                this.imageCanvasElement.className = "holaf-editor-image-canvas";
                // Style du canvas sera géré dynamiquement dans drawImagesOnDedicatedCanvas
                this.domContainer.appendChild(this.imageCanvasElement);

                // Bouton "Apply"
                this.applyButton = document.createElement("button");
                this.applyButton.textContent = "Apply & Process Downstream";
                this.applyButton.style.width = "calc(100% - 10px)"; // Laisser un peu de marge
                this.applyButton.style.marginTop = "5px";
                this.applyButton.style.marginLeft = "5px"; // Marge pour centrer
                this.applyButton.style.marginRight = "5px"; // Marge pour centrer
                this.applyButton.style.marginBottom = "5px"; // Marge en bas
                this.applyButton.style.padding = "8px";
                this.applyButton.style.cursor = "pointer";
                this.applyButton.className = "comfy-button"; // Style ComfyUI
                this.applyButton.addEventListener("click", () => {
                    // console.log(`[Holaf Editor DEBUG] Apply button clicked for node ${this.id}`);
                    if (this.properties === undefined) { this.properties = {}; }
                    // Incrémenter la propriété qui sera envoyée au backend
                    this.properties["force_process_trigger"] = (this.properties["force_process_trigger"] || 0) + 1;
                    
                    // console.log(`[Holaf Editor DEBUG] force_process_trigger new value: ${this.properties["force_process_trigger"]}`);
                    
                    this.setDirtyCanvas(true, true); // Important pour que LiteGraph envoie les nouvelles props
                    app.graph.change(); // Notifier LiteGraph d'un changement
                    app.queuePrompt(); // Lancer le prompt
                });
                this.domContainer.appendChild(this.applyButton);

                // Ajouter le conteneur DOM comme un seul widget au node
                this.mainDOMWidget = this.addDOMWidget("holaf_editor_display_widget", "div", this.domContainer, {
                    // La hauteur sera gérée par computeSize et onResize/drawImagesOnDedicatedCanvas
                });


                const onImageLoadOrError = () => {
                    this.imagesLoaded.original = this.imageOriginal.complete && this.imageOriginal.naturalWidth > 0;
                    this.imagesLoaded.modified = this.imageModified.complete && this.imageModified.naturalWidth > 0;
                    this.drawImagesOnDedicatedCanvas();
                };

                this.imageOriginal.onload = onImageLoadOrError;
                this.imageOriginal.onerror = () => { console.error(`[Holaf Editor] Original Image LOAD FAILED. URL:`, this.imageOriginal.src); onImageLoadOrError(); };
                this.imageModified.onload = onImageLoadOrError;
                this.imageModified.onerror = () => { console.error(`[Holaf Editor] Modified Image LOAD FAILED. URL:`, this.imageModified.src); onImageLoadOrError(); };

                this.imageCanvasElement.addEventListener("mousemove", (e) => this.handleCanvasMouseMove(e));
                this.imageCanvasElement.addEventListener("mouseleave", (e) => this.handleCanvasMouseLeave(e));
                this.boundWindowResizeHandler = this.handleWindowResize.bind(this);
                window.addEventListener('resize', this.boundWindowResizeHandler);

                // Initialisation si des données sont déjà là (ex: chargement de workflow)
                setTimeout(() => {
                    this.onResize(this.size); // Calcule la taille initiale du canvas
                    if (this.lastMessage) {
                        this.loadImagesFromMessage(this.lastMessage);
                    }
                }, 150);
            };

            nodeType.prototype.onRemoved = function() {
                window.removeEventListener('resize', this.boundWindowResizeHandler);
                if (this.imageOriginal) this.imageOriginal.src = "";
                if (this.imageModified) this.imageModified.src = "";
            };

            nodeType.prototype.handleWindowResize = function() {
                // Appelé lorsque la fenêtre du navigateur est redimensionnée,
                // ce qui peut affecter les dimensions calculées via getBoundingClientRect.
                setTimeout(() => {
                    if (this.imageCanvasElement && !this.flags.collapsed) {
                        this.drawImagesOnDedicatedCanvas();
                    }
                }, 50);
            };

            nodeType.prototype.loadImagesFromMessage = function(message) {
                if (!message) {
                    this.imageOriginal.src = ""; this.imageModified.src = "";
                    this.drawImagesOnDedicatedCanvas(); // Pour effacer si message null
                    return;
                }
                const uiData = message; // 'message' EST l'objet ui_info de Python

                if (!uiData) {
                    this.imageOriginal.src = ""; this.imageModified.src = "";
                    this.drawImagesOnDedicatedCanvas(); // Pour effacer si uiData null
                    return;
                }

                const arrayToString = (arr) => (Array.isArray(arr) ? arr.join('') : ((arr === null || arr === undefined) ? "" : String(arr)));

                this.imagesLoaded.original = false; this.imagesLoaded.modified = false;
                let oUrl = null, mUrl = null;

                const originalFilename = arrayToString(uiData.original_filename);
                const modifiedFilename = arrayToString(uiData.modified_filename);
                const originalSubfolder = arrayToString(uiData.original_subfolder);
                const modifiedSubfolder = arrayToString(uiData.modified_subfolder);
                const originalType = arrayToString(uiData.original_type) || 'temp';
                const modifiedType = arrayToString(uiData.modified_type) || 'temp';

                if(originalFilename) oUrl = getImageDataAsUrl({ filename: originalFilename, subfolder: originalSubfolder, type: originalType });
                if(modifiedFilename) mUrl = getImageDataAsUrl({ filename: modifiedFilename, subfolder: modifiedSubfolder, type: modifiedType });
                
                this.imageOriginal.src = oUrl || "";
                this.imageModified.src = mUrl || "";

                // drawImagesOnDedicatedCanvas() sera appelé par les callbacks onload/onerror des images
            };

            const originalOnExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                 originalOnExecuted?.apply(this, arguments); // Appel de la fonction originale si elle existe
                 this.lastMessage = message; // Stocker le message UI
                 this.loadImagesFromMessage(message); // Charger les images basées sur le message UI
            };
            
            nodeType.prototype.drawImagesOnDedicatedCanvas = function() {
                if (!this.imageCanvasElement || this.flags.collapsed || !this.domContainer || !this.mainDOMWidget || !this.mainDOMWidget.value) {
                    // console.log("[Holaf Draw] Prereqs not met for drawing (canvas, domContainer, or mainDOMWidget missing/collapsed).");
                    return;
                }
                const canvas = this.imageCanvasElement;
                const ctx = canvas.getContext("2d");
                if (!ctx) { console.error("[Holaf Editor] Failed to get 2D context!"); return; }

                // LOGS DE DÉBOGAGE POUR LA TAILLE
                // if (this.mainDOMWidget) {
                //     console.log("[Holaf Draw Sizing] mainDOMWidget.options.height (from computeSize):", this.mainDOMWidget.options?.height);
                //     console.log("[Holaf Draw Sizing] mainDOMWidget.computed_size (LiteGraph internal):", this.mainDOMWidget.computed_size);
                // }

                const dpr = window.devicePixelRatio || 1;
                const graphCanvas = app.canvas;
                const graphZoom = graphCanvas.ds.scale || 1;

                // Utiliser la taille du conteneur DOM du widget entier (this.mainDOMWidget.value est this.domContainer)
                const domWidgetRect = this.mainDOMWidget.value.getBoundingClientRect();
                const logicalWidgetWidth = domWidgetRect.width / graphZoom;
                const logicalWidgetTotalHeight = domWidgetRect.height / graphZoom;

                // Calculer la hauteur logique du bouton
                let logicalButtonHeight = 0;
                if (this.applyButton && this.applyButton.offsetHeight > 0) { // S'assurer que le bouton est visible et a une hauteur
                    const buttonStyle = getComputedStyle(this.applyButton);
                    const buttonMarginTop = parseFloat(buttonStyle.marginTop) || 0;
                    const buttonMarginBottom = parseFloat(buttonStyle.marginBottom) || 0;
                    logicalButtonHeight = (this.applyButton.offsetHeight / graphZoom) + buttonMarginTop + buttonMarginBottom;
                } else { // Fallback si le bouton n'est pas encore rendu ou est caché
                    // Utiliser l'estimation stockée dans computeSize si disponible
                    logicalButtonHeight = ( (this.mainDOMWidget.options?.buttonHeightEstimate || 40) ); // C'est déjà une estimation logique
                }
                
                const newLogicalWidth = Math.max(10, logicalWidgetWidth);
                // La hauteur logique pour le canvas est la hauteur totale du widget moins la hauteur du bouton
                const newLogicalHeight = Math.max(10, logicalWidgetTotalHeight - logicalButtonHeight);

                // LOGS DE DÉBOGAGE POUR LA TAILLE
                // console.log(`[Holaf Draw Sizing] Calculated for Canvas: W=${newLogicalWidth.toFixed(2)}, H=${newLogicalHeight.toFixed(2)}`);
                // console.log(`[Holaf Draw Sizing] --มาจาก--> DOM Widget Total H (logic): ${logicalWidgetTotalHeight.toFixed(2)}, Button H (logic): ${logicalButtonHeight.toFixed(2)}`);


                if (newLogicalWidth <= 10 || newLogicalHeight <= 10) {
                    console.warn(`[Holaf Draw Sizing] Canvas dimensions too small or zero: W=${newLogicalWidth.toFixed(2)}, H=${newLogicalHeight.toFixed(2)}. DOM Widget H: ${logicalWidgetTotalHeight.toFixed(2)}, Button H: ${logicalButtonHeight.toFixed(2)}. Clearing canvas.`);
                    ctx.clearRect(0,0,canvas.width, canvas.height); // Effacer le contenu précédent
                    // Dessiner un message d'erreur ou un placeholder dans le canvas si trop petit
                    // ctx.save();
                    // ctx.fillStyle = "red";
                    // ctx.font = "10px Arial";
                    // ctx.fillText("Canvas too small", 2, 8);
                    // ctx.restore();
                    return;
                }

                const newPhysicalWidth = Math.round(newLogicalWidth * dpr);
                const newPhysicalHeight = Math.round(newLogicalHeight * dpr);

                if (canvas.width !== newPhysicalWidth || canvas.height !== newPhysicalHeight) {
                    canvas.width = newPhysicalWidth; canvas.height = newPhysicalHeight;
                    canvas.style.width = `${newLogicalWidth}px`; canvas.style.height = `${newLogicalHeight}px`;
                }

                ctx.save(); ctx.scale(dpr, dpr);
                if (this.separatorXRatio === null && newLogicalWidth > 0) this.separatorXRatio = 0.5;
                let separatorPixelX = this.separatorXRatio * newLogicalWidth;
                separatorPixelX = Math.max(0, Math.min(separatorPixelX, newLogicalWidth));
                
                // Couleur de fond du canvas
                ctx.fillStyle = this.properties["bgcolor"] || LiteGraph.NODE_DEFAULT_BGCOLOR; // Couleur de fond du node
                ctx.fillRect(0, 0, newLogicalWidth, newLogicalHeight);


                const drawImageScaledToFit = (imgToDraw, imgName) => { 
                    if (!imgToDraw || !imgToDraw.complete || imgToDraw.naturalWidth === 0 || imgToDraw.naturalHeight === 0) return;
                    const iAR = imgToDraw.naturalWidth / imgToDraw.naturalHeight; const cAR = newLogicalWidth / newLogicalHeight;
                    let rW, rH, oX, oY;
                    if(iAR > cAR) { rW = newLogicalWidth; rH = rW / iAR; } else { rH = newLogicalHeight; rW = rH * iAR; }
                    oX = (newLogicalWidth - rW) / 2; oY = (newLogicalHeight - rH) / 2;
                    try { ctx.drawImage(imgToDraw, oX, oY, rW, rH); } catch (e) { console.error(`Error drawing ${imgName} for node ${this.id}:`, e); }
                };
                drawImageScaledToFit(this.imageOriginal, "Original");
                if (this.imageModified.complete && this.imageModified.naturalWidth > 0) { 
                    ctx.save(); ctx.beginPath(); ctx.rect(separatorPixelX, 0, newLogicalWidth - separatorPixelX, newLogicalHeight);
                    ctx.clip(); drawImageScaledToFit(this.imageModified, "Modified"); ctx.restore();
                } else if (this.imageOriginal.complete && this.imageOriginal.naturalWidth > 0 && this.imageOriginal.src) { 
                    ctx.save(); ctx.beginPath(); ctx.rect(separatorPixelX, 0, newLogicalWidth - separatorPixelX, newLogicalHeight);
                    ctx.clip(); drawImageScaledToFit(this.imageOriginal, "Original (placeholder)");
                    ctx.globalAlpha = 0.4; ctx.fillStyle = "rgba(0,0,0,0.5)"; ctx.fillRect(separatorPixelX, 0, newLogicalWidth - separatorPixelX, newLogicalHeight);
                    ctx.globalAlpha = 1.0; ctx.restore();
                }
                if (this.isMouseOverImageCanvas && (this.imagesLoaded.original || this.imagesLoaded.modified)) { 
                    ctx.save(); ctx.beginPath(); ctx.moveTo(separatorPixelX, 0); ctx.lineTo(separatorPixelX, newLogicalHeight);
                    ctx.lineWidth = Math.max(0.5, 1 / graphZoom) ; ctx.strokeStyle = "rgba(255, 255, 255, 0.8)"; ctx.stroke(); ctx.restore();
                }
                ctx.restore();
            };

            nodeType.prototype.handleCanvasMouseMove = function(event) {
                if (this.flags.collapsed || !this.imageCanvasElement) return;
                const rect = this.imageCanvasElement.getBoundingClientRect(); 
                const mouseXInCanvas = event.clientX - rect.left;
                
                this.isMouseOverImageCanvas = true; 
                if (this.imageCanvasElement) this.imageCanvasElement.style.cursor = "ew-resize";
                
                const logicalCanvasWidth = this.imageCanvasElement.clientWidth;
                if (logicalCanvasWidth > 0) { 
                    this.separatorXRatio = Math.max(0, Math.min(mouseXInCanvas / logicalCanvasWidth, 1.0));
                }
                this.drawImagesOnDedicatedCanvas();
            };

            nodeType.prototype.handleCanvasMouseLeave = function(event) {
                this.isMouseOverImageCanvas = false; 
                if (this.imageCanvasElement) this.imageCanvasElement.style.cursor = "default";
                this.drawImagesOnDedicatedCanvas();
            };

            nodeType.prototype.onMouseDown = function(event, pos, graphCanvas) {
                // Permettre l'interaction avec le canvas et le bouton
                if (this.domContainer && this.domContainer.contains(event.target)) {
                    // Si le clic est sur le canvas, on gère le ratio, sinon c'est peut-être le bouton
                    if (event.target === this.imageCanvasElement) {
                        // On pourrait ajouter une logique ici si on voulait un clic sur le canvas
                    }
                    return true; // Indique à LiteGraph que cet événement est géré par ce widget
                }
                return false; // Laisser LiteGraph gérer (ex: drag node)
            };

            nodeType.prototype.onResize = function(newSize) {
                 // newSize est [width, height] du node entier.
                 // La hauteur du widget DOM est principalement gérée par computeSize.
                 // onResize est appelé quand le node est redimensionné par l'utilisateur.
                if (this.mainDOMWidget && this.mainDOMWidget.value) {
                     this.mainDOMWidget.value.style.width = "100%"; // Assurer que le conteneur DOM prend toute la largeur
                }
                // console.log(`[Holaf onResize] Node newSize: ${newSize[0]}x${newSize[1]}`);
                setTimeout(() => this.drawImagesOnDedicatedCanvas(), 100); // Délai un peu plus long pour le DOM
                this.setDirtyCanvas(true, false);
            };

            const originalComputeSize = nodeType.prototype.computeSize;
            nodeType.prototype.computeSize = function(out) {
                // `size` est la taille actuelle du node, ou la taille par défaut si c'est la première fois.
                let size = originalComputeSize ? originalComputeSize.apply(this, arguments) : [...(this.size || [LiteGraph.NODE_WIDTH, LiteGraph.NODE_MIN_HEIGHT])];
                
                const titleHeight = LiteGraph.NODE_TITLE_HEIGHT;
                const canvasTargetLogicalHeight = 250; // Hauteur logique désirée pour la partie image
                const buttonLogicalHeightEstimate = 40; // Estimation de la hauteur logique du bouton + ses marges (top/bottom)
                const generalMargins = LiteGraph.NODE_SLOT_HEIGHT; // Marge standard en bas du node

                // Calculer la hauteur des widgets standards (sliders)
                let standardWidgetsHeight = 0;
                if (this.widgets) {
                    for(const w of this.widgets) {
                        // Exclure notre widget DOM principal de ce calcul
                        if (w.name !== "holaf_editor_display_widget") { 
                           standardWidgetsHeight += (w.height || LiteGraph.NODE_WIDGET_HEIGHT) + LiteGraph.NODE_WIDGET_PADDING;
                        }
                    }
                }
                
                // Hauteur totale que notre widget DOM (canvas + bouton) doit occuper
                const domWidgetTargetHeight = canvasTargetLogicalHeight + buttonLogicalHeightEstimate;
                
                // Calculer la hauteur totale du node
                size[1] = titleHeight + standardWidgetsHeight + domWidgetTargetHeight + generalMargins;
                // Assurer une largeur minimale pour le node
                size[0] = Math.max(size[0] || LiteGraph.NODE_WIDTH, 320); 

                // Configurer la hauteur pour le widget DOM lui-même pour que LiteGraph lui donne cet espace
                if (this.mainDOMWidget) {
                    if (!this.mainDOMWidget.options) this.mainDOMWidget.options = {};
                    // LiteGraph utilisera cette option pour déterminer la hauteur à allouer à ce widget DOM.
                    this.mainDOMWidget.options.height = domWidgetTargetHeight;
                    // Stocker l'estimation de la hauteur du bouton pour l'utiliser dans drawImagesOnDedicatedCanvas
                    // au cas où le bouton n'est pas encore rendu (offsetHeight serait 0).
                    this.mainDOMWidget.options.buttonHeightEstimate = buttonLogicalHeightEstimate; 
                }
                
                // LOGS DE DÉBOGAGE POUR LA TAILLE
                // console.log(`[Holaf ComputeSize] Calculated Node H: ${size[1].toFixed(2)}, DOMWidgetOptH: ${this.mainDOMWidget?.options?.height.toFixed(2)}, TitleH: ${titleHeight}, StdWidgetsH: ${standardWidgetsHeight.toFixed(2)}`);
                return size;
            };
        }
    },
});