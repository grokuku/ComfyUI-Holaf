/*
 * Copyright (C) 2025 Holaf
 * Logic for HolafRemote, HolafBypasser and HolafGroupBypasser nodes.
 */

import { app } from "../../scripts/app.js";

// Constants
const MODE_ALWAYS = 0;
const MODE_MUTE = 2;
const MODE_BYPASS = 4;

const HOLAF_BYPASSER_TYPE = "HolafBypasser";
const HOLAF_GROUP_BYPASSER_TYPE = "HolafGroupBypasser";
const HOLAF_REMOTE_TYPE = "HolafRemote";

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

                if (this.type === HOLAF_GROUP_BYPASSER_TYPE) {
                    this.setupGroupSelector();
                }
            };

            // --- 2. UPDATE ON LOAD ---
            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                if (onConfigure) onConfigure.apply(this, arguments);

                // Fix Label
                const groupWidget = this.widgets?.find(w => w.name === "group_name");
                const activeWidget = this.widgets?.find(w => w.name === "active");
                if (groupWidget && activeWidget) {
                    activeWidget.label = groupWidget.value || "active";
                }

                // Fix Dropdown if needed
                if (this.type === HOLAF_GROUP_BYPASSER_TYPE) {
                    // Try to populate immediately if graph is ready
                    setTimeout(() => this.setupGroupSelector(), 100);
                }

                // Fix Dynamic Slots (Restore if connections exist or logic dictates)
                if (this.type === HOLAF_BYPASSER_TYPE) {
                    // We need to delay slightly to let links be established in memory
                    setTimeout(() => this.checkDynamicSlots(), 100);
                }
            };

            // --- 3. DYNAMIC INPUTS LISTENER ---
            if (nodeData.name === HOLAF_BYPASSER_TYPE) {
                const onConnectionsChange = nodeType.prototype.onConnectionsChange;
                nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info, ...args) {
                    if (onConnectionsChange) onConnectionsChange.apply(this, [type, index, connected, link_info, ...args]);

                    // Input type is 1
                    if (type === 1) {
                        this.checkDynamicSlots();
                    }
                };

                // Logic to add slots
                nodeType.prototype.checkDynamicSlots = function () {
                    const originalSlot = this.findInputSlot("original");

                    // 1. If 'original' is connected, ensure we have at least one 'other_bypass'
                    if (originalSlot !== -1 && this.inputs[originalSlot].link !== null) {
                        const hasBypassSlot = this.inputs.some(i => i.name.startsWith("other_bypass"));
                        if (!hasBypassSlot) {
                            this.addInput("other_bypass_1", "*");
                        }
                    }

                    // 2. If the LAST 'other_bypass' slot is connected, add a new one
                    const bypassInputs = this.inputs.filter(i => i.name.startsWith("other_bypass"));
                    if (bypassInputs.length > 0) {
                        const lastBypass = bypassInputs[bypassInputs.length - 1];
                        if (lastBypass.link !== null) {
                            const nextIndex = bypassInputs.length + 1;
                            this.addInput(`other_bypass_${nextIndex}`, "*");
                        }
                    }

                    // Resize node to fit new slots if needed
                    this.setSize(this.computeSize());
                }
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

                // Initial label setup
                updateLabel(groupWidget.value);

                // Listeners
                groupWidget.callback = (value) => { updateLabel(value); };

                const originalActiveCallback = activeWidget.callback;
                activeWidget.callback = (value) => {
                    if (originalActiveCallback) originalActiveCallback(value);
                    if (IS_SYNCING) return;

                    const groupName = groupWidget.value;
                    this.syncGroupState(app.graph, groupName, value);
                    this.triggerBypassLogic(value);
                };
            };

            // --- GROUP SELECTOR LOGIC ---
            nodeType.prototype.setupGroupSelector = function () {
                const comfyGroupWidget = this.widgets.find(w => w.name === "comfy_group");
                if (!comfyGroupWidget) return;

                // Force conversion to Combo
                comfyGroupWidget.type = "combo";
                if (!comfyGroupWidget.options) comfyGroupWidget.options = {};

                const refreshGroups = () => {
                    const groups = app.graph._groups || [];
                    const names = groups.map(g => g.title).filter(t => t);
                    // Keep existing value if valid, otherwise prepend None
                    const values = ["None", ...names];
                    comfyGroupWidget.options.values = values;

                    // If current value is invalid/empty, set to None
                    if (!comfyGroupWidget.value || !values.includes(comfyGroupWidget.value)) {
                        comfyGroupWidget.value = "None";
                    }
                };

                // Initial refresh
                refreshGroups();

                // Refresh on interaction (Mouse Enter) to catch new groups created by user
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

            // --- TRIGGER LOGIC ---
            nodeType.prototype.triggerBypassLogic = function (isActive) {
                if (this.type === HOLAF_BYPASSER_TYPE) {
                    this.handleStandardBypass(isActive);
                } else if (this.type === HOLAF_GROUP_BYPASSER_TYPE) {
                    this.handleGroupBypass(isActive);
                }
            };

            // --- LOGIC 1: STANDARD BYPASSER ---
            nodeType.prototype.handleStandardBypass = function (isActive) {
                // By default for standard bypasser, we use BYPASS mode (purple)
                // Active = ON (True) -> Mode Always
                // Active = OFF (False) -> Mode Bypass
                const targetMode = isActive ? MODE_ALWAYS : MODE_BYPASS;
                const graph = this.graph;
                if (!graph) return;

                const updateLink = (linkId) => {
                    if (!linkId) return;
                    const link = graph.links[linkId];
                    if (!link) return;
                    const node = graph.getNodeById(link.origin_id);
                    // Only update if changed to avoid loop
                    if (node && node.mode !== targetMode) {
                        node.mode = targetMode;
                    }
                };

                // Original input
                const originalSlot = this.findInputSlot("original");
                if (originalSlot !== -1 && this.inputs[originalSlot].link) {
                    updateLink(this.inputs[originalSlot].link);
                }

                // Dynamic inputs
                if (this.inputs) {
                    for (const input of this.inputs) {
                        if (input.name && input.name.startsWith("other_bypass")) {
                            if (input.link) updateLink(input.link);
                        }
                    }
                }
                app.graph.change();
            };

            // --- LOGIC 2: GROUP BYPASSER (Updated with Mode Selection) ---
            nodeType.prototype.handleGroupBypass = function (isActive) {
                const comfyGroupWidget = this.widgets.find(w => w.name === "comfy_group");
                const modeWidget = this.widgets.find(w => w.name === "bypass_mode");

                if (!comfyGroupWidget || !comfyGroupWidget.value || comfyGroupWidget.value === "None") return;

                const targetGroupName = comfyGroupWidget.value;
                const graph = this.graph;

                const visualGroup = graph._groups.find(g => g.title === targetGroupName);
                if (!visualGroup) return;

                // Determine Mode: Mute (2) or Bypass (4)
                // If widget is missing (old version), default to Bypass
                let inactiveMode = MODE_BYPASS;
                if (modeWidget && modeWidget.value === "Mute") {
                    inactiveMode = MODE_MUTE;
                }

                const targetMode = isActive ? MODE_ALWAYS : inactiveMode;

                const gX = visualGroup.pos[0];
                const gY = visualGroup.pos[1];
                const gW = visualGroup.size[0];
                const gH = visualGroup.size[1];

                for (const node of graph._nodes) {
                    if (node.id === this.id) continue;
                    if ([HOLAF_BYPASSER_TYPE, HOLAF_REMOTE_TYPE, HOLAF_GROUP_BYPASSER_TYPE].includes(node.type)) continue;

                    // Check containment
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