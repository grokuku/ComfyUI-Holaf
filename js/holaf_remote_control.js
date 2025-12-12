/*
 * Copyright (C) 2025 Holaf
 * Logic for HolafRemote, HolafBypasser and HolafGroupBypasser nodes.
 */

import { app } from "../../scripts/app.js";

// Constants
const MODE_ALWAYS = 0;
const MODE_BYPASS = 4;

const HOLAF_BYPASSER_TYPE = "HolafBypasser";
const HOLAF_GROUP_BYPASSER_TYPE = "HolafGroupBypasser";
const HOLAF_REMOTE_TYPE = "HolafRemote";

// Flag to prevent infinite recursion
let IS_SYNCING = false;

app.registerExtension({
    name: "holaf.RemoteControl",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if ([HOLAF_BYPASSER_TYPE, HOLAF_REMOTE_TYPE, HOLAF_GROUP_BYPASSER_TYPE].includes(nodeData.name)) {

            // --- 1. SETUP ON CREATION ---
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);
                this.setupRemoteLogic();

                // Specific setup for Group Bypasser (Dropdown population)
                if (this.type === HOLAF_GROUP_BYPASSER_TYPE) {
                    this.setupGroupSelector();
                }
            };

            // --- 2. UPDATE ON LOAD ---
            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                if (onConfigure) onConfigure.apply(this, arguments);

                const groupWidget = this.widgets?.find(w => w.name === "group_name");
                const activeWidget = this.widgets?.find(w => w.name === "active");
                if (groupWidget && activeWidget) {
                    activeWidget.label = groupWidget.value || "active";
                }

                // For Bypasser, ensure we have dynamic slots if loaded from save
                if (this.type === HOLAF_BYPASSER_TYPE) {
                    // Logic handled by onConnectionsChange mostly, but we ensure cleanliness
                }
            };

            // --- 3. DYNAMIC INPUTS FOR BYPASSER ---
            if (nodeData.name === HOLAF_BYPASSER_TYPE) {
                const onConnectionsChange = nodeType.prototype.onConnectionsChange;
                nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info, ...args) {
                    if (onConnectionsChange) onConnectionsChange.apply(this, [type, index, connected, link_info, ...args]);

                    // Only care about Input connections (type 1)
                    if (type !== 1) return;

                    // Logic to add "other_bypass" slots
                    // We check if the last "bypass" slot has a link. If yes, we add a new one.
                    const inputs = this.inputs || [];
                    const lastInput = inputs[inputs.length - 1];

                    // Check if we need to ADD a slot
                    if (lastInput && lastInput.link !== null) {
                        // Add new slot
                        const nextIndex = inputs.length - 2; // -2 because of original + alternative? No, names are dynamic.
                        // Actually easier: just count how many "other_bypass" we have
                        const bypassCount = inputs.filter(i => i.name.startsWith("other_bypass")).length;
                        this.addInput(`other_bypass_${bypassCount + 1}`, "*");
                    }

                    // Logic to REMOVE trailing empty slots (optional, to keep it clean)
                    // We iterate from end. If slot is empty AND it's an "other_bypass" AND the one before is empty too...
                    // Let's keep it simple: Just ensure we always have exactly ONE empty "other_bypass" at the end.
                    // (Skipped for now to avoid complexity/flickering, purely additive is safer).
                };
            }


            // --- CORE LOGIC ---
            nodeType.prototype.setupRemoteLogic = function () {
                const groupWidget = this.widgets.find(w => w.name === "group_name");
                const activeWidget = this.widgets.find(w => w.name === "active");

                if (!groupWidget || !activeWidget) return;

                const updateLabel = (text) => {
                    activeWidget.label = text || "active";
                    this.setDirtyCanvas(true, true);
                };
                updateLabel(groupWidget.value);

                groupWidget.callback = (value) => {
                    updateLabel(value);
                };

                const originalActiveCallback = activeWidget.callback;
                activeWidget.callback = (value) => {
                    if (originalActiveCallback) originalActiveCallback(value);
                    if (IS_SYNCING) return;

                    const groupName = groupWidget.value;
                    this.syncGroupState(app.graph, groupName, value);

                    // Trigger specific logic for this node immediately
                    this.triggerBypassLogic(value);
                };
            };

            // --- GROUP SELECTOR LOGIC (Dropdown) ---
            nodeType.prototype.setupGroupSelector = function () {
                const comfyGroupWidget = this.widgets.find(w => w.name === "comfy_group");
                if (!comfyGroupWidget) return;

                // Convert text widget to Combo
                comfyGroupWidget.type = "combo";
                comfyGroupWidget.options = { values: [] };

                // Function to refresh the list of groups
                const refreshGroups = () => {
                    const groups = app.graph._groups || [];
                    const names = groups.map(g => g.title).filter(t => t);
                    names.unshift("None");
                    comfyGroupWidget.options.values = names;
                };

                // Refresh on mouse enter to ensure list is up to date
                this.onMouseEnter = function (e) {
                    refreshGroups();
                };
            };


            // --- SYNC ENGINE ---
            nodeType.prototype.syncGroupState = function (targetGraph, groupName, newState) {
                const wasSyncing = IS_SYNCING;
                IS_SYNCING = true;

                try {
                    const traverse = (graph) => {
                        if (!graph || !graph._nodes) return;
                        for (const node of graph._nodes) {
                            if (node === this) continue;
                            if (node.subgraph) traverse(node.subgraph);

                            if ([HOLAF_BYPASSER_TYPE, HOLAF_REMOTE_TYPE, HOLAF_GROUP_BYPASSER_TYPE].includes(node.type)) {
                                const otherGroupWidget = node.widgets.find(w => w.name === "group_name");
                                const otherActiveWidget = node.widgets.find(w => w.name === "active");

                                if (otherGroupWidget && otherActiveWidget && otherGroupWidget.value === groupName) {
                                    otherActiveWidget.value = newState;
                                    node.triggerBypassLogic(newState);
                                }
                            }
                        }
                    };
                    if (!wasSyncing) traverse(targetGraph);
                } finally {
                    if (!wasSyncing) IS_SYNCING = false;
                }
            };

            // --- TRIGGER LOGIC (Dispatcher) ---
            nodeType.prototype.triggerBypassLogic = function (isActive) {
                if (this.type === HOLAF_BYPASSER_TYPE) {
                    this.handleStandardBypass(isActive);
                } else if (this.type === HOLAF_GROUP_BYPASSER_TYPE) {
                    this.handleGroupBypass(isActive);
                }
            };

            // --- LOGIC 1: STANDARD BYPASSER (Inputs based) ---
            nodeType.prototype.handleStandardBypass = function (isActive) {
                const targetMode = isActive ? MODE_ALWAYS : MODE_BYPASS;
                const graph = this.graph;
                if (!graph) return;

                // Helper to update a link
                const updateLink = (linkId) => {
                    if (!linkId) return;
                    const link = graph.links[linkId];
                    if (!link) return;
                    const node = graph.getNodeById(link.origin_id);
                    if (node && node.mode !== targetMode) {
                        node.mode = targetMode;
                    }
                };

                // Check 'original'
                const originalSlot = this.findInputSlot("original");
                if (originalSlot !== -1 && this.inputs[originalSlot].link) {
                    updateLink(this.inputs[originalSlot].link);
                }

                // Check all dynamic 'other_bypass_X'
                if (this.inputs) {
                    for (const input of this.inputs) {
                        if (input.name && input.name.startsWith("other_bypass")) {
                            if (input.link) updateLink(input.link);
                        }
                    }
                }
                app.graph.change();
            };

            // --- LOGIC 2: GROUP BYPASSER (Visual Group based) ---
            nodeType.prototype.handleGroupBypass = function (isActive) {
                const comfyGroupWidget = this.widgets.find(w => w.name === "comfy_group");
                if (!comfyGroupWidget || !comfyGroupWidget.value || comfyGroupWidget.value === "None") return;

                const targetGroupName = comfyGroupWidget.value;
                const graph = this.graph; // Use local graph (subgraph safe)

                // Find the visual group object
                const visualGroup = graph._groups.find(g => g.title === targetGroupName);
                if (!visualGroup) return;

                const targetMode = isActive ? MODE_ALWAYS : MODE_BYPASS;

                // Bounding box check
                const gX = visualGroup.pos[0];
                const gY = visualGroup.pos[1];
                const gW = visualGroup.size[0];
                const gH = visualGroup.size[1];

                // Iterate over all nodes in this graph
                for (const node of graph._nodes) {
                    // Skip self and other controllers to avoid recursion or disabling the controller itself!
                    if (node.id === this.id) continue;
                    if ([HOLAF_BYPASSER_TYPE, HOLAF_REMOTE_TYPE, HOLAF_GROUP_BYPASSER_TYPE].includes(node.type)) continue;

                    // Check if node center is inside group
                    // Or top-left? Usually Comfy uses "is contained".
                    // Let's check if the node's position is strictly inside the group rect.
                    if (node.pos[0] >= gX && node.pos[0] <= gX + gW &&
                        node.pos[1] >= gY && node.pos[1] <= gY + gH) {

                        if (node.mode !== targetMode) {
                            node.mode = targetMode;
                        }
                    }
                }
                app.graph.change();
            };
        }
    }
});