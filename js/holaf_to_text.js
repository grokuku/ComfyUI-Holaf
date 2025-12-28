import { app } from "../../scripts/app.js";
import { ComfyWidgets } from "../../scripts/widgets.js";

app.registerExtension({
    name: "Holaf.ToText",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "HolafToText") {
            
            // 1. Create the text display widget on node creation
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                // Create a read-only text widget
                // parameters: name, value, type, options
                const w = ComfyWidgets.STRING(this, "display_text", ["STRING", { multiline: true }], app).widget;
                w.inputEl.readOnly = true;
                w.inputEl.style.opacity = 0.6; // Visual cue that it's read-only
                
                return r;
            };

            // 2. Update the widget when the server sends the text
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);

                if (message && message.text) {
                    // Find the widget named "display_text" (created above) or the first text widget
                    const widget = this.widgets.find((w) => w.name === "display_text");
                    if (widget) {
                        widget.value = message.text[0]; // Update value
                        this.onResize?.(this.size); // Force redraw if needed
                    }
                }
            };
        }
    },
});