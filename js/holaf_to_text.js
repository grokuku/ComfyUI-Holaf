import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

app.registerExtension({
    name: "Holaf.ToText",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "HolafToText") {

            // --- 1. RENDER HELPERS (CORRIGÉ & COMPACT) ---
            const renderMarkdown = (text) => {
                if (!text) return "";
                
                let html = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n');

                // 1. Sécurité HTML
                html = html
                    .replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;");

                // 2. Éléments de Bloc
                html = html
                    // Headers : Marges très compactes
                    .replace(/^### (.*$)/gim, '<h3 style="margin:4px 0 1px 0; font-size:1.1em; font-weight:bold; color:#e0e0e0; border-bottom:1px solid #444;">$1</h3>')
                    .replace(/^## (.*$)/gim, '<h2 style="margin:6px 0 2px 0; font-size:1.2em; font-weight:bold; color:#fff; border-bottom:1px solid #555;">$1</h2>')
                    .replace(/^# (.*$)/gim, '<h1 style="margin:8px 0 3px 0; font-size:1.4em; font-weight:bold; color:#fff; border-bottom:1px solid #777;">$1</h1>')
                    
                    // Séparateur
                    .replace(/^---$/gim, '<hr style="border:0; border-top:1px solid #555; margin:6px 0;">')

                    // Listes : Flexbox + Marges réduites (2px au lieu de 4px)
                    .replace(/^\s*[\-\*] (.*$)/gim, 
                        '<div style="display:flex; align-items:flex-start; margin-bottom:2px;">' +
                            '<span style="display:inline-block; width:5px; height:5px; border-radius:50%; background-color:#888; margin-top:6px; margin-right:8px; flex-shrink:0;"></span>' +
                            '<span style="color:#ddd; flex:1;">$1</span>' +
                        '</div>');

                // 3. Éléments en ligne
                html = html
                    .replace(/\*\*(.*?)\*\*/g, '<strong style="color:#fff; font-weight:700;">$1</strong>')
                    .replace(/`([^`]+)`/g, '<code style="background:#333; color:#ff9f89; padding:1px 4px; border-radius:3px; font-family:monospace;">$1</code>');

                // 4. NETTOYAGE CRITIQUE DES SAUTS DE LIGNE
                // On supprime le \n qui suit immédiatement nos blocs (div de liste, headers)
                // pour éviter le double saut de ligne (Bloc + <br>)
                html = html.replace(/(<\/div>|<\/h[1-3]>|<\/hr>)\s*\n/g, '$1');

                // 5. Conversion des \n RESTANTS uniquement (paragraphes normaux)
                html = html.replace(/\n/g, '<br>');

                return html;
            };

            const updateWidgetVisuals = (el, text, mode) => {
                if (!el) return;
                
                el.style.whiteSpace = "pre-wrap"; 
                el.style.fontFamily = "monospace";
                
                if (mode === "Markdown") {
                    el.innerHTML = renderMarkdown(text);
                    el.style.fontFamily = "Segoe UI, Tahoma, sans-serif";
                    el.style.whiteSpace = "normal"; 
                } else if (mode === "JSON") {
                    el.innerHTML = `<pre style="margin:0; color:#8ec07c; font-family:monospace; font-size:11px;">${text}</pre>`;
                    el.style.whiteSpace = "pre";
                } else {
                    el.textContent = text;
                }
            };

            // --- 2. SETUP ---
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                ComfyWidgets.STRING(this, "display_text", ["STRING", { multiline: true }], app);
                this.custom_widget_el = null; 
                this.last_display_mode = "Plain";
                return r;
            };

            // --- 3. HIGH PERFORMANCE CHECK LOOP ---
            const onDrawForeground = nodeType.prototype.onDrawForeground;
            nodeType.prototype.onDrawForeground = function (ctx) {
                onDrawForeground?.apply(this, arguments);

                const widget = this.widgets?.find((w) => w.name === "display_text");
                if (!widget || !widget.inputEl || !widget.inputEl.parentNode) return;

                if (widget.inputEl.holaf_patched) return;

                // --- DOM INJECTION ---
                widget.inputEl.style.display = "none";
                
                const myDiv = document.createElement("div");
                myDiv.className = "holaf-totext-custom comfy-multiline-input";
                Object.assign(myDiv.style, {
                    width: "100%",
                    height: "100%",
                    minHeight: "150px", 
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
                    cursor: "text",
                    marginTop: "5px"
                });

                widget.inputEl.parentNode.appendChild(myDiv);
                this.custom_widget_el = myDiv;
                widget.inputEl.holaf_patched = true; 
                
                updateWidgetVisuals(myDiv, widget.value || "", this.last_display_mode);
            };

            // --- 4. DATA UPDATE ---
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);

                if (message && message.text) {
                    const widget = this.widgets.find((w) => w.name === "display_text");
                    
                    if (widget) {
                        const text = message.text[0];
                        const mode = message.mode ? message.mode[0] : "Plain";
                        
                        widget.value = text;
                        this.last_display_mode = mode;

                        if (this.custom_widget_el && this.custom_widget_el.isConnected) {
                            updateWidgetVisuals(this.custom_widget_el, text, mode);
                        } else {
                            if (widget.inputEl) widget.inputEl.holaf_patched = false;
                        }
                        
                        this.onResize?.(this.size);
                    }
                }
            };
        }
    },
});