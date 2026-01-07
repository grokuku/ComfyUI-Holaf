/*
 * Copyright (C) 2025 Holaf
 * Logic for HolafRemote, HolafBypasser, HolafGroupBypasser and HolafRemoteSelector nodes.
 */

import { app } from "../../scripts/app.js";

// Constants
const MODE_ALWAYS = 0;
const MODE_MUTE = 2;
const MODE_BYPASS = 4;

const HOLAF_BYPASSER_TYPE = "HolafBypasser";
const HOLAF_GROUP_BYPASSER_TYPE = "HolafGroupBypasser";
const HOLAF_REMOTE_TYPE = "HolafRemote";
const HOLAF_REMOTE_SELECTOR_TYPE = "HolafRemoteSelector";

let IS_SYNCING = false;

app.registerExtension({
    name: "holaf.RemoteControl",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if ([HOLAF_BYPASSER_TYPE, HOLAF_REMOTE_TYPE, HOLAF_GROUP_BYPASSER_TYPE, HOLAF_REMOTE_SELECTOR_TYPE].includes(nodeData.name)) {

            // --- 1. SETUP ON CREATION ---
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);

                if (this.type === HOLAF_REMOTE_SELECTOR_TYPE) {
                    this.setupRemoteSelectorLogic();
                } else {
                    this.setupRemoteLogic();
                }

                if (this.type === HOLAF_GROUP_BYPASSER_TYPE) {
                    this.setupGroupSelector();
                }
            };

            // --- 2. UPDATE ON LOAD ---
            const onConfigure = nodeType.prototype.onConfigure;
            nodeType.prototype.onConfigure = function () {
                if (onConfigure) onConfigure.apply(this, arguments);

                // Fix Label for standard Remotes
                if (this.type !== HOLAF_REMOTE_SELECTOR_TYPE) {
                    const groupWidget = this.widgets?.find(w => w.name === "group_name");
                    const activeWidget = this.widgets?.find(w => w.name === "active");
                    if (groupWidget && activeWidget) {
                        activeWidget.label = groupWidget.value || "active";
                    }
                }

                // Setup Group Selector immediately
                if (this.type === HOLAF_GROUP_BYPASSER_TYPE) {
                    this.setupGroupSelector();
                }

                // Setup Remote Selector logic immediately (restore dropdown options)
                if (this.type === HOLAF_REMOTE_SELECTOR_TYPE) {
                    // Use setTimeout to ensure widgets are fully loaded/restored before swapping
                    setTimeout(() => {
                        this.setupRemoteSelectorLogic();
                    }, 50);
                }

                // Fix Dynamic Slots
                if (this.type === HOLAF_BYPASSER_TYPE) {
                    setTimeout(() => this.checkDynamicSlots(), 100);
                }
            };

            // --- 3. DYNAMIC INPUTS LISTENER ---
            if (nodeData.name === HOLAF_BYPASSER_TYPE) {
                const onConnectionsChange = nodeType.prototype.onConnectionsChange;
                nodeType.prototype.onConnectionsChange = function (type, index, connected, link_info, ...args) {
                    if (onConnectionsChange) onConnectionsChange.apply(this, [type, index, connected, link_info, ...args]);
                    if (type === 1) {
                        this.checkDynamicSlots();
                    }
                };

                nodeType.prototype.checkDynamicSlots = function () {
                    const originalSlot = this.findInputSlot("original");

                    if (originalSlot !== -1 && this.inputs[originalSlot].link !== null) {
                        const hasBypassSlot = this.inputs.some(i => i.name.startsWith("other_bypass"));
                        if (!hasBypassSlot) {
                            this.addInput("other_bypass_1", "*");
                        }
                    }

                    const bypassInputs = this.inputs.filter(i => i.name.startsWith("other_bypass"));
                    if (bypassInputs.length > 0) {
                        const lastBypass = bypassInputs[bypassInputs.length - 1];
                        if (lastBypass.link !== null) {
                            const nextIndex = bypassInputs.length + 1;
                            this.addInput(`other_bypass_${nextIndex}`, "*");
                        }
                    }
                    this.setSize(this.computeSize());
                }
            }


            // --- CORE LOGIC : STANDARD REMOTE ---
            nodeType.prototype.setupRemoteLogic = function () {
                // Ensure this logic doesn't run for the Selector
                if (this.type === HOLAF_REMOTE_SELECTOR_TYPE) return;

                const groupWidget = this.widgets.find(w => w.name === "group_name");
                const activeWidget = this.widgets.find(w => w.name === "active");

                if (!groupWidget || !activeWidget) return;

                const updateLabel = (text) => {
                    activeWidget.label = text || "active";
                    this.setDirtyCanvas(true, true);
                };

                updateLabel(groupWidget.value);
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

            // --- CORE LOGIC : REMOTE SELECTOR (NEW) ---
            nodeType.prototype.setupRemoteSelectorLogic = function () {
                const listWidget = this.widgets.find(w => w.name === "group_list");
                let activeWidgetIndex = this.widgets.findIndex(w => w.name === "active_group");
                let activeWidget = this.widgets[activeWidgetIndex];

                if (!listWidget || !activeWidget) return;

                // --- KEY FIX: FORCE WIDGET REPLACEMENT ---
                // If the widget is still a text input (STRING), we destroy it and create a proper COMBO widget.
                if (activeWidget.type !== "combo") {
                    const currentValue = activeWidget.value;

                    // Remove the old text widget
                    this.widgets.splice(activeWidgetIndex, 1);

                    // Create configuration for the new combo widget
                    // We initialize it with empty values, they will be populated by updateDropdownOptions
                    const newWidget = this.addWidget("combo", "active_group", currentValue, (v) => { }, { values: [] });

                    // Ensure the new widget is in the correct variable for the rest of the function
                    activeWidget = newWidget;
                }

                // Parser function: Updates the dropdown options based on the text list
                const updateDropdownOptions = () => {
                    const text = listWidget.value || "";
                    const lines = text.split("\n").map(s => s.trim()).filter(s => s);

                    // Update options on the combo widget
                    activeWidget.options.values = lines;

                    // Validation: if current selection is invalid or empty, default to first available
                    if (lines.length > 0 && !lines.includes(activeWidget.value)) {
                        // Optional: Force a valid value if current is invalid. 
                        // Useful for initial setup.
                        if (activeWidget.value === "") {
                            activeWidget.value = lines[0];
                        }
                    }
                };

                // Listener on the List Widget
                listWidget.callback = (v) => {
                    updateDropdownOptions();
                    this.setDirtyCanvas(true, true);
                };

                // Logic on Selection Change
                // We assign the callback directly to the (potentially new) widget
                activeWidget.callback = (value) => {
                    if (IS_SYNCING) return;

                    const allGroups = listWidget.value.split("\n").map(s => s.trim()).filter(s => s);

                    allGroups.forEach(groupName => {
                        const isActive = (groupName === value);
                        this.syncGroupState(app.graph, groupName, isActive);
                    });
                };

                // Initial run to populate the list based on current text
                updateDropdownOptions();
            };

            // --- GROUP SELECTOR LOGIC (Simplified) ---
            nodeType.prototype.setupGroupSelector = function () {
                const comfyGroupWidget = this.widgets.find(w => w.name === "comfy_group");
                if (!comfyGroupWidget) return;

                // Function to refresh the list of groups
                const refreshGroups = () => {
                    const groups = app.graph._groups || [];
                    const names = groups.map(g => g.title).filter(t => t);

                    // Always ensure "None" is first
                    const values = ["None", ...names];
                    comfyGroupWidget.options.values = values;
                };

                // Refresh immediately
                refreshGroups();

                // Refresh on interaction
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
                // HolafRemote and HolafRemoteSelector have no internal bypass logic to trigger
            };

            // --- LOGIC 1: STANDARD BYPASSER ---
            nodeType.prototype.handleStandardBypass = function (isActive) {
                const targetMode = isActive ? MODE_ALWAYS : MODE_BYPASS;
                const graph = this.graph;
                if (!graph) return;

                const updateLink = (linkId) => {
                    if (!linkId) return;
                    const link = graph.links[linkId];
                    if (!link) return;
                    const node = graph.getNodeById(link.origin_id);
                    if (node && node.mode !== targetMode) {
                        node.mode = targetMode;
                    }
                };

                const originalSlot = this.findInputSlot("original");
                if (originalSlot !== -1 && this.inputs[originalSlot].link) {
                    updateLink(this.inputs[originalSlot].link);
                }

                if (this.inputs) {
                    for (const input of this.inputs) {
                        if (input.name && input.name.startsWith("other_bypass")) {
                            if (input.link) updateLink(input.link);
                        }
                    }
                }
                app.graph.change();
            };

            // --- LOGIC 2: GROUP BYPASSER ---
            nodeType.prototype.handleGroupBypass = function (isActive) {
                const comfyGroupWidget = this.widgets.find(w => w.name === "comfy_group");
                const modeWidget = this.widgets.find(w => w.name === "bypass_mode");

                if (!comfyGroupWidget || !comfyGroupWidget.value || comfyGroupWidget.value === "None") return;

                const targetGroupName = comfyGroupWidget.value;
                const graph = this.graph;

                const visualGroup = graph._groups.find(g => g.title === targetGroupName);
                if (!visualGroup) return;

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