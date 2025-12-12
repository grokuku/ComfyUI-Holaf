/*
 * Copyright (C) 2025 Holaf
 * Logic for HolafShortcut nodes.
 */

import { app } from "../../scripts/app.js";

const HOLAF_SHORTCUT_TYPE = "HolafShortcut";
const HOLAF_SHORTCUT_USER_TYPE = "HolafShortcutUser";

app.registerExtension({
    name: "holaf.Shortcut",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === HOLAF_SHORTCUT_TYPE || nodeData.name === HOLAF_SHORTCUT_USER_TYPE) {
            
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);

                if (this.type === HOLAF_SHORTCUT_TYPE) {
                    this.setupShortcutNode();
                } else if (this.type === HOLAF_SHORTCUT_USER_TYPE) {
                    this.setupUserNode();
                }
            };

            // --- 1. SHORTCUT NODE (Anchor) ---
            nodeType.prototype.setupShortcutNode = function() {
                // Initialize properties to store view data if not exists
                if (!this.properties) this.properties = {};
                if (!this.properties.saved_view) {
                    this.properties.saved_view = null;
                }

                // Add "Save Position" Button
                this.addWidget("button", "📍 Save Position", null, (widget, canvas, node, pos, event) => {
                    const ds = app.canvas.ds;
                    
                    // We save the current scale and offset directly.
                    // This captures exactly what the user is seeing.
                    const viewData = {
                        scale: ds.scale,
                        offset: [...ds.offset] // Clone array to avoid reference issues
                    };
                    
                    this.properties.saved_view = viewData;
                    
                    // Visual feedback (change button text temporarily)
                    const originalName = widget.name;
                    widget.name = "✅ Saved!";
                    this.setDirtyCanvas(true, true);
                    setTimeout(() => {
                        widget.name = originalName;
                        this.setDirtyCanvas(true, true);
                    }, 1000);
                });
            };

            // --- 2. USER NODE (Remote) ---
            nodeType.prototype.setupUserNode = function() {
                // Add "Jump" Button
                this.addWidget("button", "🚀 Jump", null, (widget, canvas, node, pos, event) => {
                    this.triggerJump();
                });
            };

            // Logic to perform the jump
            nodeType.prototype.triggerJump = function() {
                const targetWidget = this.widgets.find(w => w.name === "target_shortcut");
                if (!targetWidget || !targetWidget.value) return;

                const targetName = targetWidget.value;
                const graph = app.graph;

                // Find the target node
                let targetNode = null;
                for (const node of graph._nodes) {
                    if (node.type === HOLAF_SHORTCUT_TYPE) {
                        const nameWidget = node.widgets.find(w => w.name === "shortcut_name");
                        if (nameWidget && nameWidget.value === targetName) {
                            targetNode = node;
                            break;
                        }
                    }
                }

                if (targetNode) {
                    const savedView = targetNode.properties?.saved_view;
                    if (savedView) {
                        // Apply view
                        app.canvas.ds.scale = savedView.scale;
                        app.canvas.ds.offset = [...savedView.offset];
                        app.canvas.setDirty(true, true);
                    } else {
                        alert(`Shortcut "${targetName}" found, but no position saved yet.\nPlease click "Save Position" on the target node.`);
                    }
                } else {
                    alert(`Shortcut named "${targetName}" not found.`);
                }
            };
        }
    }
});