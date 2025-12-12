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

                    // We start syncing from the root graph, but the function handles recursion
                    this.syncGroupState(app.graph, groupName, value);

                    // Specific logic for Bypasser: Handle the upstream node
                    if (this.type === HOLAF_BYPASSER_TYPE) {
                        this.updateUpstreamNode(value);
                    }
                };
            };

            // Main function to sync all nodes in the same group (Recursive)
            nodeType.prototype.syncGroupState = function (targetGraph, groupName, newState) {
                // Only set flag if we are at the root call to avoid blocking nested calls if implemented poorly,
                // but here we just set it once globally.
                const wasSyncing = IS_SYNCING;
                IS_SYNCING = true;

                try {
                    // Internal traversal function
                    const traverse = (graph) => {
                        if (!graph || !graph._nodes) return;

                        for (const node of graph._nodes) {
                            // Skip self by object reference to avoid infinite loops on the trigger node
                            if (node === this) continue;

                            // --- CASE 1: The node is a Subgraph / Group Node ---
                            // If the node has a 'subgraph' property, we must dive into it.
                            if (node.subgraph) {
                                traverse(node.subgraph);
                            }

                            // --- CASE 2: The node is a Holaf Target ---
                            if (node.type === HOLAF_BYPASSER_TYPE || node.type === HOLAF_REMOTE_TYPE) {
                                const otherGroupWidget = node.widgets.find(w => w.name === "group_name");
                                const otherActiveWidget = node.widgets.find(w => w.name === "active");

                                if (otherGroupWidget && otherActiveWidget) {
                                    if (otherGroupWidget.value === groupName) {
                                        otherActiveWidget.value = newState;

                                        // If the other node is a Bypasser, trigger its upstream logic
                                        if (node.type === HOLAF_BYPASSER_TYPE) {
                                            // Ensure we call it within the context of that specific node
                                            node.updateUpstreamNode(newState);
                                        }
                                    }
                                }
                            }
                        }
                    };

                    // Start traversal from the provided graph (usually app.graph)
                    if (!wasSyncing) {
                        traverse(targetGraph);
                    }

                } finally {
                    if (!wasSyncing) IS_SYNCING = false;
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

                // CRITICAL FIX FOR SUBGRAPHS:
                // Use 'this.graph' instead of 'app.graph' to find links. 
                // Inside a subgraph, the links belong to the subgraph, not the main app graph.
                const graph = this.graph;
                if (!graph || !graph.links) return;

                const link = graph.links[linkId];
                if (!link) return;

                const upstreamNode = graph.getNodeById(link.origin_id);
                if (!upstreamNode) return;

                const targetMode = isActive ? MODE_BYPASS : MODE_ALWAYS;

                if (upstreamNode.mode !== targetMode) {
                    upstreamNode.mode = targetMode;

                    // Visually update the graph (requires finding the canvas for that graph usually, 
                    // but app.graph.change() usually triggers a global redraw).
                    app.graph.change();
                }
            };
        }
    }
});