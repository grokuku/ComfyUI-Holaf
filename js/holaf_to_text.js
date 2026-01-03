import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

app.registerExtension({
    name: "Holaf.ToText",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "HolafToText") {
            
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                // 1. Create the standard ComfyUI text widget
                const w = ComfyWidgets.STRING(this, "display_text", ["STRING", { multiline: true }], app).widget;
                
                // Flag to trigger the swap once the element is ready
                this.dom_widget_replaced = false;
                
                return r;
            };

            // 2. Hook into the draw loop to check for DOM availability
            const onDrawForeground = nodeType.prototype.onDrawForeground;
            nodeType.prototype.onDrawForeground = function (ctx) {
                onDrawForeground?.apply(this, arguments);

                if (!this.dom_widget_replaced) {
                    const widget = this.widgets.find((w) => w.name === "display_text");
                    
                    // Check if widget exists and has an element attached to the DOM (has a parent)
                    if (widget && widget.inputEl && widget.inputEl.parentNode) {
                        
                        // Create our Custom DIV
                        const displayDiv = document.createElement("div");
                        displayDiv.className = "comfy-multiline-input"; // Keep Comfy styling
                        
                        Object.assign(displayDiv.style, {
                            width: "100%",
                            height: "100%",
                            overflowY: "auto",
                            padding: "8px",
                            boxSizing: "border-box",
                            backgroundColor: "#222",
                            color: "#ddd",
                            fontSize: "12px",
                            fontFamily: "monospace",
                            lineHeight: "1.4",
                            whiteSpace: "pre-wrap",
                            wordBreak: "break-word",
                            userSelect: "text",
                            border: "1px solid #444",
                            borderRadius: "4px",
                            cursor: "text"
                        });

                        // 3. EXECUTE SWAP
                        widget.inputEl.parentNode.replaceChild(displayDiv, widget.inputEl);
                        
                        // Update reference so future updates target the DIV
                        widget.inputEl = displayDiv;
                        
                        // Mark as done
                        this.dom_widget_replaced = true;
                        
                        // Restore previous value if any (handled in onExecuted usually, but good practice)
                        if (widget.value) {
                             displayDiv.textContent = widget.value;
                        }
                    }
                }
            };

            const renderMarkdown = (text) => {
                if (!text) return "";
                return text
                    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
                    .replace(/^### (.*$)/gim, '<h3 style="color:#fff; margin:8px 0 4px 0; border-bottom:1px solid #555; font-size:14px;">$1</h3>')
                    .replace(/^## (.*$)/gim, '<h2 style="color:#fff; margin:10px 0 5px 0; border-bottom:1px solid #666; font-size:16px;">$1</h2>')
                    .replace(/^# (.*$)/gim, '<h1 style="color:#fff; margin:12px 0 6px 0; border-bottom:1px solid #777; font-size:18px;">$1</h1>')
                    .replace(/\*\*(.*)\*\*/gim, '<b style="color:#fff; font-weight:bold;">$1</b>')
                    .replace(/`(.*?)`/gim, '<code style="background:#333; padding:1px 4px; border-radius:3px; font-family:monospace; color:#ff7b72;">$1</code>')
                    .replace(/^\- (.*$)/gim, '<div style="margin-left:15px; display:list-item; list-style-type: disc;">$1</div>')
                    .replace(/\n/gim, '<br>');
            };

            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);

                if (message && message.text) {
                    const widget = this.widgets.find((w) => w.name === "display_text");
                    
                    if (widget && widget.inputEl) {
                        const text = message.text[0];
                        const mode = message.mode ? message.mode[0] : "Plain";
                        const el = widget.inputEl;

                        // Ensure we are working with our DIV (in case swap happened late)
                        if (el.tagName !== "DIV") {
                            // If we are here, swap hasn't happened yet, value will be set, 
                            // and the swap in onDrawForeground will pick it up later.
                            widget.value = text;
                            return; 
                        }

                        if (mode === "Markdown") {
                            el.innerHTML = renderMarkdown(text);
                            el.style.fontFamily = "Segoe UI, Tahoma, sans-serif";
                            el.style.whiteSpace = "normal";
                        } else if (mode === "JSON") {
                            el.innerHTML = `<pre style="margin:0; color:#8ec07c; font-family:monospace; font-size:11px;">${text}</pre>`;
                            el.style.whiteSpace = "pre";
                            el.style.fontFamily = "monospace";
                        } else {
                            el.textContent = text;
                            el.style.fontFamily = "monospace";
                            el.style.whiteSpace = "pre-wrap";
                        }
                        
                        // Clean up UI
                        widget.label = null; 
                        this.onResize?.(this.size);
                    }
                }
            };
        }
    },
});