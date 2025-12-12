/*
 * Copyright (C) 2025 Holaf
 * Logic for HolafRemote and HolafBypasser nodes.
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

// Constants for Node Modes in ComfyUI
const MODE_ALWAYS = 0;
const MODE_MUTE = 2;
const MODE_BYPASS = 4;

const HOLAF_BYPASSER_TYPE = "HolafBypasser";
const HOLAF_REMOTE_TYPE = "HolafRemote";

// Flag to prevent infinite recursion when syncing widgets
let IS_SYNCING = false;

app.registerExtension({
    name: "holaf.RemoteControl",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === HOLAF_BYPASSER_TYPE || nodeData.name === HOLAF_REMOTE_TYPE) {

            // Hook into the node creation to setup listeners
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) {
                    onNodeCreated.apply(this, arguments);
                }

                this.setupRemoteLogic();
            };

            // Define the custom logic method attached to the node instance
            nodeType.prototype.setupRemoteLogic = function () {
                // Find widgets
                const groupWidget = this.widgets.find(w => w.name === "group_name");
                const activeWidget = this.widgets.find(w => w.name === "active");

                if (!groupWidget || !activeWidget) return;

                // Callback when 'active' toggle is clicked
                const originalActiveCallback = activeWidget.callback;
                activeWidget.callback = (value) => {
                    if (originalActiveCallback) originalActiveCallback(value);
                    if (IS_SYNCING) return; // Stop recursion

                    const groupName = groupWidget.value;
                    this.syncGroupState(groupName, value);

                    // Specific logic for Bypasser: Handle the upstream node
                    if (this.type === HOLAF_BYPASSER_TYPE) {
                        this.updateUpstreamNode(value);
                    }
                };

                // Callback when 'group_name' changes (optional: sync immediately to new group state?)
                // For now, we just let it change. If user toggles active, it will affect the new group.
            };

            // Main function to sync all nodes in the same group
            nodeType.prototype.syncGroupState = function (groupName, newState) {
                IS_SYNCING = true;
                try {
                    const graph = app.graph;
                    for (const node of graph._nodes) {
                        if (node.id === this.id) continue; // Skip self

                        if (node.type === HOLAF_BYPASSER_TYPE || node.type === HOLAF_REMOTE_TYPE) {
                            const otherGroupWidget = node.widgets.find(w => w.name === "group_name");
                            const otherActiveWidget = node.widgets.find(w => w.name === "active");

                            if (otherGroupWidget && otherActiveWidget) {
                                if (otherGroupWidget.value === groupName) {
                                    // Update value without firing callback recursively? 
                                    // Actually we WANT to fire callback for Bypasser to update upstream, 
                                    // but we blocked recursion via IS_SYNCING.
                                    // However, modifying .value directly doesn't fire callback.

                                    otherActiveWidget.value = newState;

                                    // If the other node is a Bypasser, we must manually trigger its upstream logic
                                    // because we are bypassing the widget callback via direct assignment (or if we called callback, IS_SYNCING blocks it).
                                    if (node.type === HOLAF_BYPASSER_TYPE) {
                                        node.updateUpstreamNode(newState);
                                    }
                                }
                            }
                        }
                    }
                } finally {
                    IS_SYNCING = false;
                }
            };

            // Function to Bypass/Unbypass the parent node connected to 'original'
            nodeType.prototype.updateUpstreamNode = function (isActive) {
                // Only for Bypasser nodes
                if (this.type !== HOLAF_BYPASSER_TYPE) return;

                // Find the input slot named "original"
                const originalInputIndex = this.findInputSlot("original");
                if (originalInputIndex === -1) return;

                const inputData = this.inputs[originalInputIndex];
                if (!inputData || !inputData.link) return;

                const linkId = inputData.link;
                const link = app.graph.links[linkId];
                if (!link) return;

                const upstreamNode = app.graph.getNodeById(link.origin_id);
                if (!upstreamNode) return;

                // LOGIC:
                // If Remote is ACTIVE (True) -> We are using the ALTERNATIVE path.
                // This means the ORIGINAL path is NOT needed.
                // So we set the Upstream Node to BYPASS (or MUTE).
                // User requested: "Active -> node parent reliée a l'entrée anything soit bypass"

                const targetMode = isActive ? MODE_BYPASS : MODE_ALWAYS;

                if (upstreamNode.mode !== targetMode) {
                    upstreamNode.mode = targetMode;

                    // Visually update the graph to show the change (graying out/bypassing)
                    app.graph.change();
                }
            };
        }
    }
});