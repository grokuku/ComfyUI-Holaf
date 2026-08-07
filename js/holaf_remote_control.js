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

// IS_SYNCING prevents recursive group state synchronization.
// JavaScript is single-threaded, so this flag is sufficient.
// Scoped per-graph to avoid interference across multiple graph instances.
const _holafSyncingPerGraph = new WeakMap();

// Tracks HOST widgets (a Holaf widget promoted onto a SubgraphNode) whose
// callback has been chained by this extension, together with their original
// store-backed callback so it can be restored on widget-demoted.
// Keyed by the host widget instance (WeakMap => no leaks on removal).
const _holafChainedHostWidgets = new WeakMap();

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

                this.setupSubgraphListener();
            };

            // --- 1b. SUBGRAPH LISTENER LIFECYCLE ---
            // Bind/unbind the subgraph promotion listeners whenever the node is
            // (re)attached to a graph or removed. onAdded fires both when creating
            // a node and when it is dragged into a subgraph (onAdded is called with
            // this.graph already set to the Subgraph instance).
            const onAdded = nodeType.prototype.onAdded;
            nodeType.prototype.onAdded = function () {
                if (onAdded) onAdded.apply(this, arguments);
                this.setupSubgraphListener();
            };

            const onRemoved = nodeType.prototype.onRemoved;
            nodeType.prototype.onRemoved = function () {
                if (this._holafSubgraphAbortController) {
                    this._holafSubgraphAbortController.abort();
                    this._holafSubgraphAbortController = null;
                }
                if (onRemoved) onRemoved.apply(this, arguments);
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

                this.setupSubgraphListener();
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
                    this.runRemoteLogic(value);
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

                    // addWidget appends to the end of the list; move the new widget
                    // back to its original position so the visual widget order is preserved.
                    const insertedIndex = this.widgets.indexOf(newWidget);
                    if (insertedIndex !== activeWidgetIndex) {
                        this.widgets.splice(insertedIndex, 1);
                        this.widgets.splice(activeWidgetIndex, 0, newWidget);
                    }

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
                    this.runRemoteLogic(value);
                };

                // Initial run to populate the list based on current text
                updateDropdownOptions();
            };

            // --- SHARED REMOTE LOGIC ---
            // Single source of truth for the "active" / "active_group" state
            // propagation. Used by the interior widget callbacks (non-promoted
            // nodes) AND by the chained host widget callback (promoted nodes).
            nodeType.prototype.runRemoteLogic = function (value) {
                if (_holafSyncingPerGraph.get(app.graph)) return;

                if (this.type === HOLAF_REMOTE_SELECTOR_TYPE) {
                    const listWidget = this.widgets.find(w => w.name === "group_list");
                    if (!listWidget) return;

                    const allGroups = listWidget.value.split("\n").map(s => s.trim()).filter(s => s);

                    allGroups.forEach(groupName => {
                        const isActive = (groupName === value);
                        this.syncGroupState(app.graph, groupName, isActive);
                    });
                } else {
                    const groupWidget = this.widgets.find(w => w.name === "group_name");
                    if (!groupWidget) return;

                    this.syncGroupState(app.graph, groupWidget.value, value);
                    this.triggerBypassLogic(value);
                }
            };

            // --- SUBGRAPH WIDGET PROMOTION SYNC ---
            // Since ComfyUI frontend >= 1.41.20, when a Holaf widget ("active" /
            // "active_group") is promoted into a subgraph, the store-backed host
            // widget on the SubgraphNode only writes to useWidgetValueStore and no
            // longer calls the interior widget callback, so syncGroupState() and
            // triggerBypassLogic() never run.
            //
            // Events are dispatched on subgraph.events with
            // { widget, subgraphNode } (see docs.comfy.org/custom-nodes/js/subgraphs).
            // We chain the HOST widget callback: original store write first, then
            // the usual runRemoteLogic() (syncGroupState + triggerBypassLogic).
            nodeType.prototype.setupSubgraphListener = function () {
                // Rebind idempotently: abort any previous listener first.
                if (this._holafSubgraphAbortController) {
                    this._holafSubgraphAbortController.abort();
                    this._holafSubgraphAbortController = null;
                }

                const subgraph = this.graph;
                // A Subgraph exposes `inputNode`; the root graph does not. This is
                // how we only listen on subgraphs containing this node.
                if (!subgraph || !subgraph.inputNode || !subgraph.events ||
                    typeof subgraph.events.addEventListener !== 'function') return;

                const controller = new AbortController();
                this._holafSubgraphAbortController = controller;
                const { signal } = controller;

                subgraph.events.addEventListener('widget-promoted', (e) => {
                    const interiorWidget = e.detail?.widget;
                    const hostNode = e.detail?.subgraphNode;
                    if (!interiorWidget || !hostNode) return;

                    // Only handle widgets belonging to this node (identity check:
                    // the event carries the same widget object as node.widgets).
                    if (!this.widgets || !this.widgets.includes(interiorWidget)) return;
                    if (interiorWidget.name !== 'active' && interiorWidget.name !== 'active_group') return;

                    const hostInput = this.findPromotedHostInput(hostNode, interiorWidget);
                    if (!hostInput) return;

                    const hostWidget = hostInput._widget || hostNode.getWidgetFromSlot?.(hostInput);
                    if (!hostWidget || typeof hostWidget.callback !== 'function') return;

                    // Anti-doublon: never chain the same host widget twice.
                    if (_holafChainedHostWidgets.has(hostWidget)) return;

                    const originalCallback = hostWidget.callback;
                    _holafChainedHostWidgets.set(hostWidget, { originalCallback });

                    hostWidget.callback = (value) => {
                        // 1. Original store-backed write (useWidgetValueStore).
                        originalCallback(value);
                        // 2. Then the usual sync + bypass logic on this interior node.
                        this.runRemoteLogic(value);
                    };
                }, { signal });

                subgraph.events.addEventListener('widget-demoted', (e) => {
                    const widget = e.detail?.widget;
                    const hostNode = e.detail?.subgraphNode;
                    if (!widget) return;

                    // On demotion the payload widget is the projected HOST widget.
                    let hostWidget = _holafChainedHostWidgets.has(widget) ? widget : null;

                    // Fallback: resolve the host widget from the subgraph node inputs
                    // (covers payloads carrying the interior widget instead).
                    if (!hostWidget && hostNode && hostNode.inputs) {
                        const hostInput = hostNode.inputs.find(input =>
                            (input.widget && input.widget.name === widget.name) ||
                            input.name === widget.name
                        );
                        if (hostInput) {
                            hostWidget = hostInput._widget || hostNode.getWidgetFromSlot?.(hostInput) || null;
                        }
                    }

                    if (!hostWidget) return;
                    const entry = _holafChainedHostWidgets.get(hostWidget);
                    if (!entry) return;

                    hostWidget.callback = entry.originalCallback;
                    _holafChainedHostWidgets.delete(hostWidget);
                }, { signal });
            };

            // Finds the host input on a SubgraphNode for a promoted interior widget.
            // Primary match resolves the actual subgraph slot connection (robust even
            // when the input was renamed / uniquified, e.g. "active2"); falls back to
            // a unique name match for the common widget-name promotion case.
            nodeType.prototype.findPromotedHostInput = function (hostNode, interiorWidget) {
                const inputs = hostNode.inputs || [];
                if (inputs.length === 0) return null;

                for (const input of inputs) {
                    const slot = input._subgraphSlot;
                    if (!slot || typeof slot.getConnectedWidgets !== 'function') continue;
                    if (slot.getConnectedWidgets().includes(interiorWidget)) return input;
                }

                const name = interiorWidget.name;
                const sameName = inputs.filter(input =>
                    (input.widget && input.widget.name === name) || input.name === name
                );
                return sameName.length === 1 ? sameName[0] : null;
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
                if (!_holafSyncingPerGraph.has(targetGraph)) _holafSyncingPerGraph.set(targetGraph, false);
                const wasSyncing = _holafSyncingPerGraph.get(targetGraph);
                _holafSyncingPerGraph.set(targetGraph, true);

                try {
                    const traverse = (graph) => {
                        // Guard: ensure graph is a valid object with an array of nodes before traversing.
                        if (!graph || typeof graph !== 'object' || !Array.isArray(graph._nodes)) return;
                        for (const node of graph._nodes) {
                            if (node === this) continue;
                            if (node.subgraph && typeof node.subgraph === 'object') traverse(node.subgraph);

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
                    if (!wasSyncing) _holafSyncingPerGraph.set(targetGraph, false);
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

                    // Use node center for more accurate hit-testing
                    const cx = node.pos[0] + (node.size?.[0] || 0) / 2;
                    const cy = node.pos[1] + (node.size?.[1] || 0) / 2;
                    if (cx >= gX && cx <= gX + gW && cy >= gY && cy <= gY + gH) {

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