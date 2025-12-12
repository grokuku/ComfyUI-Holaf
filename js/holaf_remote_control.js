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
            nodeType.prototype.setupRemoteLogic = function() {
                // Find widgets
                const groupWidget = this.widgets.find(w => w.name === "group_name");
                // Back to looking for "active"
                const activeWidget = this.widgets.find(w => w.name === "active");

                if (!groupWidget || !activeWidget) return;

                // Callback when 'active' toggle is clicked
                const originalCallback = activeWidget.callback;
                activeWidget.callback = (value) => {
                    if (originalCallback) originalCallback(value);
                    if (IS_SYNCING) return; // Stop recursion
                    
                    const groupName = groupWidget.value;
                    
                    // We start syncing from the root graph
                    this.syncGroupState(app.graph, groupName, value);
                    
                    // Specific logic for Bypasser: Handle the upstream node
                    if (this.type === HOLAF_BYPASSER_TYPE) {
                        this.updateUpstreamNode(value);
                    }
                };
            };

            // Main function to sync all nodes in the same group (Recursive)
            nodeType.prototype.syncGroupState = function(targetGraph, groupName, newState) {
                const wasSyncing = IS_SYNCING;
                IS_SYNCING = true;
                
                try {
                    const traverse = (graph) => {
                        if (!graph || !graph._nodes) return;

                        for (const node of graph._nodes) {
                            if (node === this) continue; 

                            if (node.subgraph) {
                                traverse(node.subgraph);
                            }

                            if (node.type === HOLAF_BYPASSER_TYPE || node.type === HOLAF_REMOTE_TYPE) {
                                const otherGroupWidget = node.widgets.find(w => w.name === "group_name");
                                const otherActiveWidget = node.widgets.find(w => w.name === "active");

                                if (otherGroupWidget && otherActiveWidget) {
                                    if (otherGroupWidget.value === groupName) {
                                        otherActiveWidget.value = newState;

                                        if (node.type === HOLAF_BYPASSER_TYPE) {
                                            node.updateUpstreamNode(newState);
                                        }
                                    }
                                }
                            }
                        }
                    };

                    if (!wasSyncing) {
                        traverse(targetGraph);
                    }

                } finally {
                    if (!wasSyncing) IS_SYNCING = false;
                }
            };

            // Function to Bypass/Unbypass the parent node connected to 'original'
            nodeType.prototype.updateUpstreamNode = function(isActive) {
                if (this.type !== HOLAF_BYPASSER_TYPE) return;

                const originalInputIndex = this.findInputSlot("original");
                if (originalInputIndex === -1) return;

                const inputData = this.inputs[originalInputIndex];
                if (!inputData || !inputData.link) return;

                const linkId = inputData.link;
                
                const graph = this.graph; 
                if (!graph || !graph.links) return;

                const link = graph.links[linkId];
                if (!link) return;

                const upstreamNode = graph.getNodeById(link.origin_id);
                if (!upstreamNode) return;

                // LOGIC INVERTED HERE:
                // Active ON (True) -> Node Mode = ALWAYS (0) -> It Works.
                // Active OFF (False) -> Node Mode = BYPASS (4) -> It is skipped.
                const targetMode = isActive ? MODE_ALWAYS : MODE_BYPASS;

                if (upstreamNode.mode !== targetMode) {
                    upstreamNode.mode = targetMode;
                    app.graph.change(); 
                }
            };
        }
    }
});