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

            // Restore state on load (Crucial for correct labels after reload)
            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                if (onConfigure) onConfigure.apply(this, arguments);
                
                if (this.type === HOLAF_SHORTCUT_USER_TYPE) {
                    // Update the button label immediately after loading values
                    this.updateJumpButtonLabel();
                }
            };

            // --- 1. SHORTCUT NODE (Anchor) ---
            nodeType.prototype.setupShortcutNode = function() {
                if (!this.properties) this.properties = {};
                if (!this.properties.saved_view) {
                    this.properties.saved_view = null;
                }

                this.addWidget("button", "📍 Save Position", null, (widget, canvas, node, pos, event) => {
                    const ds = app.canvas.ds;
                    const viewData = {
                        scale: ds.scale,
                        offset: [...ds.offset]
                    };
                    this.properties.saved_view = viewData;
                    
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
                // Create the button with a default name
                this.addWidget("button", "🚀 Jump", null, (widget, canvas, node, pos, event) => {
                    this.triggerJump();
                });

                // Setup listener for dynamic renaming
                const targetWidget = this.widgets.find(w => w.name === "target_shortcut");
                if (targetWidget) {
                    const originalCallback = targetWidget.callback;
                    targetWidget.callback = (value) => {
                        if (originalCallback) originalCallback(value);
                        // Update button label when text changes
                        this.updateJumpButtonLabel(value);
                    };
                }
                
                // Initial update on creation
                this.updateJumpButtonLabel();
            };

            // Helper to rename the button based on input value
            nodeType.prototype.updateJumpButtonLabel = function(newValue) {
                const targetWidget = this.widgets.find(w => w.name === "target_shortcut");
                const jumpBtn = this.widgets.find(w => w.type === "button"); // Find the jump button
                
                if (targetWidget && jumpBtn) {
                    // Use provided value or current widget value
                    const name = newValue || targetWidget.value || "???";
                    
                    // Update the button name to be explicit
                    // "🚀 Jump to Step 1"
                    const newName = `🚀 Jump to ${name}`;
                    
                    if (jumpBtn.name !== newName) {
                        jumpBtn.name = newName;
                        this.setDirtyCanvas(true, true);
                    }
                }
            };

            // Logic to perform the jump
            nodeType.prototype.triggerJump = function() {
                const targetWidget = this.widgets.find(w => w.name === "target_shortcut");
                if (!targetWidget || !targetWidget.value) return;

                const targetName = targetWidget.value;
                const graph = app.graph;

                let targetNode = null;
                // Search for anchor node
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