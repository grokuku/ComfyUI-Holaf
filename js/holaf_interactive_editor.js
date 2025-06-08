/**
 * @file This script defines the frontend logic for the 'HolafInteractiveImageEditor' node.
 * It creates a custom DOM-based widget that displays an original and a modified image
 * side-by-side with a draggable separator. The node also includes an "Apply" button
 * that triggers the backend processing for downstream nodes.
 *
 * This implementation uses a custom <canvas> element within a DOM widget to handle
 * image drawing and interactions, providing a responsive and interactive user experience.
 */
import { app } from "../../../scripts/app.js";
import { api } from "../../../scripts/api.js";

/**
 * Constructs a valid URL for fetching a preview image from the ComfyUI server.
 * @param {object} image_data - An object containing filename, type, and subfolder.
 * @returns {string|null} The full image URL or null if data is invalid.
 */
function getImageDataAsUrl(image_data) {
    if (!image_data || !image_data.filename || typeof image_data.filename !== 'string') { return null; }
    const url = api.apiURL(`/view?filename=${encodeURIComponent(image_data.filename)}&type=${encodeURIComponent(image_data.type || 'output')}&subfolder=${encodeURIComponent(image_data.subfolder || '')}${app.getPreviewFormatParam()}${app.getRandParam()}`);
    return url;
}

const HolafInteractiveEditorNodeType = "HolafInteractiveImageEditor";

app.registerExtension({
    name: "Holaf.InteractiveImageEditor",
    async beforeRegisterNodeDef(nodeType, nodeData, appInstance) {
        if (nodeData.name === HolafInteractiveEditorNodeType) {

            // The foreground is entirely managed by the DOM widget, so this is empty.
            nodeType.prototype.onDrawForeground = function(ctx, graphCanvas) { /* Handled by DOM widget */ };

            /**
             * Initializes the node, creating the DOM structure for the editor.
             */
            nodeType.prototype.onNodeCreated = function () {
                this.imageOriginal = new Image();
                this.imageModified = new Image();
                this.imagesLoaded = { original: false, modified: false };
                this.separatorXRatio = 0.5;
                this.isMouseOverImageCanvas = false;
                this.lastMessage = null; // Stores the last UI data from the backend.

                // Main container for the canvas and button.
                this.domContainer = document.createElement("div");
                this.domContainer.className = "holaf-editor-dom-container";
                this.domContainer.style.width = "100%";
                this.domContainer.style.display = "flex";
                this.domContainer.style.flexDirection = "column";
                this.domContainer.style.minHeight = "50px";

                // Canvas for image display.
                this.imageCanvasElement = document.createElement("canvas");
                this.imageCanvasElement.className = "holaf-editor-image-canvas";
                this.domContainer.appendChild(this.imageCanvasElement);

                // "Apply" button to trigger downstream processing.
                this.applyButton = document.createElement("button");
                this.applyButton.textContent = "Apply & Process Downstream";
                this.applyButton.style.width = "calc(100% - 10px)";
                this.applyButton.style.marginTop = "5px";
                this.applyButton.style.marginLeft = "5px";
                this.applyButton.style.marginRight = "5px";
                this.applyButton.style.marginBottom = "5px";
                this.applyButton.style.padding = "8px";
                this.applyButton.style.cursor = "pointer";
                this.applyButton.className = "comfy-button";
                this.applyButton.addEventListener("click", () => {
                    if (this.properties === undefined) { this.properties = {}; }
                    // Increment a property to signal a change to the backend.
                    this.properties["force_process_trigger"] = (this.properties["force_process_trigger"] || 0) + 1;
                    
                    this.setDirtyCanvas(true, true); // Notify LiteGraph of property change.
                    app.graph.change();
                    app.queuePrompt();
                });
                this.domContainer.appendChild(this.applyButton);

                // Add the DOM container as a single widget to the node.
                this.mainDOMWidget = this.addDOMWidget("holaf_editor_display_widget", "div", this.domContainer, {});

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

                // Initial setup after a short delay to ensure the node is fully initialized.
                setTimeout(() => {
                    this.onResize(this.size);
                    if (this.lastMessage) {
                        this.loadImagesFromMessage(this.lastMessage);
                    }
                }, 150);
            };

            /**
             * Cleans up resources when the node is removed.
             */
            nodeType.prototype.onRemoved = function() {
                window.removeEventListener('resize', this.boundWindowResizeHandler);
                if (this.imageOriginal) this.imageOriginal.src = "";
                if (this.imageModified) this.imageModified.src = "";
            };

            /**
             * Handles browser window resize events to redraw the canvas correctly.
             */
            nodeType.prototype.handleWindowResize = function() {
                setTimeout(() => {
                    if (this.imageCanvasElement && !this.flags.collapsed) {
                        this.drawImagesOnDedicatedCanvas();
                    }
                }, 50);
            };

            /**
             * Loads original and modified images based on data received from the backend.
             * @param {object} message - The UI data object from the Python node's execution result.
             */
            nodeType.prototype.loadImagesFromMessage = function(message) {
                if (!message) {
                    this.imageOriginal.src = ""; this.imageModified.src = "";
                    this.drawImagesOnDedicatedCanvas();
                    return;
                }
                const uiData = message;

                if (!uiData) {
                    this.imageOriginal.src = ""; this.imageModified.src = "";
                    this.drawImagesOnDedicatedCanvas();
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
                // Redrawing is handled by the image onload/onerror callbacks.
            };

            const originalOnExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                 originalOnExecuted?.apply(this, arguments);
                 this.lastMessage = message;
                 this.loadImagesFromMessage(message);
            };
            
            /**
             * Main drawing function. Renders the images, separator, and handles scaling.
             */
            nodeType.prototype.drawImagesOnDedicatedCanvas = function() {
                if (!this.imageCanvasElement || this.flags.collapsed || !this.domContainer || !this.mainDOMWidget || !this.mainDOMWidget.value) {
                    return;
                }
                const canvas = this.imageCanvasElement;
                const ctx = canvas.getContext("2d");
                if (!ctx) { console.error("[Holaf Editor] Failed to get 2D context!"); return; }

                const dpr = window.devicePixelRatio || 1;
                const graphCanvas = app.canvas;
                const graphZoom = graphCanvas.ds.scale || 1;

                // Use the size of the DOM widget container.
                const domWidgetRect = this.mainDOMWidget.value.getBoundingClientRect();
                const logicalWidgetWidth = domWidgetRect.width / graphZoom;
                const logicalWidgetTotalHeight = domWidgetRect.height / graphZoom;

                // Calculate the logical height of the button.
                let logicalButtonHeight = 0;
                if (this.applyButton && this.applyButton.offsetHeight > 0) {
                    const buttonStyle = getComputedStyle(this.applyButton);
                    const buttonMarginTop = parseFloat(buttonStyle.marginTop) || 0;
                    const buttonMarginBottom = parseFloat(buttonStyle.marginBottom) || 0;
                    logicalButtonHeight = (this.applyButton.offsetHeight / graphZoom) + buttonMarginTop + buttonMarginBottom;
                } else {
                    // Fallback to the estimate from computeSize if the button isn't rendered yet.
                    logicalButtonHeight = ( (this.mainDOMWidget.options?.buttonHeightEstimate || 40) );
                }
                
                const newLogicalWidth = Math.max(10, logicalWidgetWidth);
                const newLogicalHeight = Math.max(10, logicalWidgetTotalHeight - logicalButtonHeight);

                if (newLogicalWidth <= 10 || newLogicalHeight <= 10) {
                    console.warn(`[Holaf Draw Sizing] Canvas dimensions too small or zero. Clearing canvas.`);
                    ctx.clearRect(0,0,canvas.width, canvas.height);
                    return;
                }

                const newPhysicalWidth = Math.round(newLogicalWidth * dpr);
                const newPhysicalHeight = Math.round(newLogicalHeight * dpr);

                if (canvas.width !== newPhysicalWidth || canvas.height !== newPhysicalHeight) {
                    canvas.width = newPhysicalWidth; canvas.height = newPhysicalHeight;
                    canvas.style.width = `${newLogicalWidth}px`; canvas.style.height = `${newLogicalHeight}px`;
                }

                ctx.save();
                ctx.scale(dpr, dpr);
                if (this.separatorXRatio === null && newLogicalWidth > 0) this.separatorXRatio = 0.5;
                let separatorPixelX = this.separatorXRatio * newLogicalWidth;
                separatorPixelX = Math.max(0, Math.min(separatorPixelX, newLogicalWidth));
                
                // Background color.
                ctx.fillStyle = this.properties["bgcolor"] || LiteGraph.NODE_DEFAULT_BGCOLOR;
                ctx.fillRect(0, 0, newLogicalWidth, newLogicalHeight);

                const drawImageScaledToFit = (imgToDraw, imgName) => { 
                    if (!imgToDraw || !imgToDraw.complete || imgToDraw.naturalWidth === 0 || imgToDraw.naturalHeight === 0) return;
                    const iAR = imgToDraw.naturalWidth / imgToDraw.naturalHeight; const cAR = newLogicalWidth / newLogicalHeight;
                    let rW, rH, oX, oY;
                    if(iAR > cAR) { rW = newLogicalWidth; rH = rW / iAR; } else { rH = newLogicalHeight; rW = rH * iAR; }
                    oX = (newLogicalWidth - rW) / 2; oY = (newLogicalHeight - rH) / 2;
                    try { ctx.drawImage(imgToDraw, oX, oY, rW, rH); } catch (e) { console.error(`Error drawing ${imgName} for node ${this.id}:`, e); }
                };

                // Draw original image.
                drawImageScaledToFit(this.imageOriginal, "Original");
                
                // Draw modified image (clipped).
                if (this.imageModified.complete && this.imageModified.naturalWidth > 0) { 
                    ctx.save(); ctx.beginPath(); ctx.rect(separatorPixelX, 0, newLogicalWidth - separatorPixelX, newLogicalHeight);
                    ctx.clip(); drawImageScaledToFit(this.imageModified, "Modified"); ctx.restore();
                } else if (this.imageOriginal.complete && this.imageOriginal.naturalWidth > 0 && this.imageOriginal.src) { 
                    // Draw a placeholder if the modified image isn't available.
                    ctx.save(); ctx.beginPath(); ctx.rect(separatorPixelX, 0, newLogicalWidth - separatorPixelX, newLogicalHeight);
                    ctx.clip(); drawImageScaledToFit(this.imageOriginal, "Original (placeholder)");
                    ctx.globalAlpha = 0.4; ctx.fillStyle = "rgba(0,0,0,0.5)"; ctx.fillRect(separatorPixelX, 0, newLogicalWidth - separatorPixelX, newLogicalHeight);
                    ctx.globalAlpha = 1.0; ctx.restore();
                }

                // Draw separator line on hover.
                if (this.isMouseOverImageCanvas && (this.imagesLoaded.original || this.imagesLoaded.modified)) { 
                    ctx.save(); ctx.beginPath(); ctx.moveTo(separatorPixelX, 0); ctx.lineTo(separatorPixelX, newLogicalHeight);
                    ctx.lineWidth = Math.max(0.5, 1 / graphZoom) ; ctx.strokeStyle = "rgba(255, 255, 255, 0.8)"; ctx.stroke(); ctx.restore();
                }
                ctx.restore();
            };

            /**
             * Handles mouse movement over the canvas to update the separator position.
             */
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

            /**
             * Handles the mouse leaving the canvas area.
             */
            nodeType.prototype.handleCanvasMouseLeave = function(event) {
                this.isMouseOverImageCanvas = false; 
                if (this.imageCanvasElement) this.imageCanvasElement.style.cursor = "default";
                this.drawImagesOnDedicatedCanvas();
            };

            /**
             * Captures mouse down events to allow interaction with the widget.
             */
            nodeType.prototype.onMouseDown = function(event, pos, graphCanvas) {
                if (this.domContainer && this.domContainer.contains(event.target)) {
                    // This indicates to LiteGraph that the event is handled by this widget.
                    return true;
                }
                // Let LiteGraph handle other events (e.g., dragging the node).
                return false;
            };

            /**
             * Redraws the canvas when the node is resized.
             */
            nodeType.prototype.onResize = function(newSize) {
                if (this.mainDOMWidget && this.mainDOMWidget.value) {
                     this.mainDOMWidget.value.style.width = "100%";
                }
                setTimeout(() => this.drawImagesOnDedicatedCanvas(), 100);
                this.setDirtyCanvas(true, false);
            };

            const originalComputeSize = nodeType.prototype.computeSize;
            /**
             * Calculates the total size of the node, including the space for the custom DOM widget.
             */
            nodeType.prototype.computeSize = function(out) {
                let size = originalComputeSize ? originalComputeSize.apply(this, arguments) : [...(this.size || [LiteGraph.NODE_WIDTH, LiteGraph.NODE_MIN_HEIGHT])];
                
                const titleHeight = LiteGraph.NODE_TITLE_HEIGHT;
                const canvasTargetLogicalHeight = 250; // Desired logical height for the image area.
                const buttonLogicalHeightEstimate = 40; // Estimated logical height for the button and its margins.
                const generalMargins = LiteGraph.NODE_SLOT_HEIGHT;

                // Calculate height of standard (non-DOM) widgets.
                let standardWidgetsHeight = 0;
                if (this.widgets) {
                    for(const w of this.widgets) {
                        if (w.name !== "holaf_editor_display_widget") { 
                           standardWidgetsHeight += (w.height || LiteGraph.NODE_WIDGET_HEIGHT) + LiteGraph.NODE_WIDGET_PADDING;
                        }
                    }
                }
                
                // Total target height for our DOM widget (canvas + button).
                const domWidgetTargetHeight = canvasTargetLogicalHeight + buttonLogicalHeightEstimate;
                
                // Calculate the final height of the entire node.
                size[1] = titleHeight + standardWidgetsHeight + domWidgetTargetHeight + generalMargins;
                size[0] = Math.max(size[0] || LiteGraph.NODE_WIDTH, 320); 

                // Configure the DOM widget's height so LiteGraph allocates the correct space.
                if (this.mainDOMWidget) {
                    if (!this.mainDOMWidget.options) this.mainDOMWidget.options = {};
                    this.mainDOMWidget.options.height = domWidgetTargetHeight;
                    // Store the button height estimate for use in the drawing function.
                    this.mainDOMWidget.options.buttonHeightEstimate = buttonLogicalHeightEstimate; 
                }
                
                return size;
            };
        }
    },
});