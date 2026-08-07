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
                        // Piste 2: If the "active" widget is promoted (its slot
                        // is linked from outside the SubgraphNode), the promoted
                        // slot drives the value — don't overwrite the label.
                        const isPromoted = this.getSlotFromWidget && this.getSlotFromWidget(activeWidget)?.link != null;
                        if (!isPromoted) {
                            activeWidget.label = groupWidget.value || "active";
                        }
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
                    if (_holafSyncingPerGraph.get(app.graph)) return;

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
                    if (_holafSyncingPerGraph.get(app.graph)) return;

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

/*
 * Piste 3 — SubgraphWatcher
 *
 * When a Holaf widget is promoted to the SubgraphNode and the user toggles it
 * there, BaseWidget.setValue() calls node.onWidgetChanged(name, value, oldValue,
 * widget) on the SubgraphNode. We wrap that hook to detect changes on promoted
 * Holaf widgets and forward them to the interior Holaf node, mirroring exactly
 * what the in-graph widget callback (setupRemoteLogic / setupRemoteSelectorLogic)
 * does for the non-promoted case.
 *
 * Coexistence:
 *   - Non-promoted: click interior widget -> interior callback -> sync/bypass
 *   - Promoted:     click SubgraphNode widget -> onWidgetChanged -> watcher
 *                   -> holafOnPromotedValueChange -> sync/bypass
 */

// Module-level: resolve the interior Holaf node(s) behind a promoted widget.
function holafHandlePromotedChange(subgraphNode, widgetName, newValue) {
    // The promoted widget name becomes the input slot name on the SubgraphNode.
    const input = subgraphNode.inputs.find(i => i.name === widgetName);
    if (!input || !input._subgraphSlot) return; // not a promoted input

    // Skip if the slot is linked from outside — the value is being driven
    // externally (e.g. by another node), not toggled by the user on the
    // SubgraphNode widget. In that case the interior node should not be
    // forced to follow.
    if (input.link != null) return;

    const subgraph = subgraphNode.subgraph;
    if (!subgraph) return;

    const holafTypes = [
        HOLAF_BYPASSER_TYPE,
        HOLAF_REMOTE_TYPE,
        HOLAF_GROUP_BYPASSER_TYPE,
        HOLAF_REMOTE_SELECTOR_TYPE
    ];

    // Each promoted input keeps a reference to its SubgraphInput slot, whose
    // linkIds point at interior links inside the subgraph. Resolve them to
    // find the interior node that actually owns the original widget.
    for (const linkId of input._subgraphSlot.linkIds) {
        const link = (typeof subgraph.getLink === "function")
            ? subgraph.getLink(linkId)
            : subgraph._links?.get(linkId);
        if (!link) continue;

        const interiorNode = subgraph.getNodeById(link.target_id);
        if (!interiorNode) continue;
        if (!holafTypes.includes(interiorNode.type)) continue;

        holafOnPromotedValueChange(interiorNode, newValue);
    }

    // Keep the host widget label in sync after a promoted toggle (matters for
    // the RemoteSelector, whose promoted "active_group" value is the label).
    holafUpdatePromotedLabels(subgraphNode);
}

// Module-level: apply the promoted toggle to the interior Holaf node, mirroring
// the in-graph widget callback logic. Shares the same reentrance guard
// (_holafSyncingPerGraph) as syncGroupState to prevent recursive loops.
function holafOnPromotedValueChange(interiorNode, newValue) {
    // Use the root graph for the reentrance guard, consistent with the
    // non-promoted callbacks that use app.graph.
    const graph = app.graph || interiorNode.graph?.rootGraph;
    if (!graph) return;

    // Reentrance guard — same mechanism as syncGroupState.
    if (_holafSyncingPerGraph.get(graph)) return;

    if (interiorNode.type === HOLAF_REMOTE_SELECTOR_TYPE) {
        const listWidget = interiorNode.widgets?.find(w => w.name === "group_list");
        const activeWidget = interiorNode.widgets?.find(w => w.name === "active_group");
        if (!listWidget || !activeWidget) return;

        activeWidget.value = newValue;

        const allGroups = listWidget.value.split("\n").map(s => s.trim()).filter(s => s);
        allGroups.forEach(groupName => {
            const isActive = (groupName === newValue);
            interiorNode.syncGroupState(graph, groupName, isActive);
        });
    } else {
        // HolafBypasser / HolafRemote / HolafGroupBypasser
        const groupWidget = interiorNode.widgets?.find(w => w.name === "group_name");
        const activeWidget = interiorNode.widgets?.find(w => w.name === "active");
        if (!groupWidget || !activeWidget) return;

        activeWidget.value = newValue;
        interiorNode.syncGroupState(graph, groupWidget.value, newValue);
        interiorNode.triggerBypassLogic(newValue);
    }
}

// Module-level: fix the label of promoted Holaf host widgets on a SubgraphNode
// so they display the interior node's group_name (or active group for the
// selector) instead of the raw input name ("active"/"active_group") that
// ComfyUI assigns during promotion (SubgraphNode._setWidget registers the
// host widget with `label: input.label ?? subgraphInput.name`).
function holafUpdatePromotedLabels(subgraphNode) {
    try {
        if (!subgraphNode || !subgraphNode.isSubgraphNode || !subgraphNode.isSubgraphNode()) return;
        const subgraph = subgraphNode.subgraph;
        if (!subgraph) return;

        const holafTypes = [
            HOLAF_BYPASSER_TYPE,
            HOLAF_REMOTE_TYPE,
            HOLAF_GROUP_BYPASSER_TYPE,
            HOLAF_REMOTE_SELECTOR_TYPE
        ];

        for (const input of subgraphNode.inputs || []) {
            // Only promoted inputs carry a _subgraphSlot reference.
            if (!input._subgraphSlot) continue;

            // Resolve the interior Holaf node behind this promoted input,
            // mirroring the link resolution used in holafHandlePromotedChange.
            let interiorNode = null;
            for (const linkId of input._subgraphSlot.linkIds || []) {
                const link = (typeof subgraph.getLink === "function")
                    ? subgraph.getLink(linkId)
                    : subgraph._links?.get(linkId);
                if (!link) continue;
                const node = subgraph.getNodeById(link.target_id);
                if (node && holafTypes.includes(node.type)) {
                    interiorNode = node;
                    break;
                }
            }
            if (!interiorNode) continue;

            // Determine the label to display from the interior node.
            let groupLabel = null;
            if (interiorNode.type === HOLAF_REMOTE_SELECTOR_TYPE) {
                const activeGroupWidget = interiorNode.widgets?.find(w => w.name === "active_group");
                groupLabel = activeGroupWidget?.value || null;
            } else {
                const groupWidget = interiorNode.widgets?.find(w => w.name === "group_name");
                groupLabel = groupWidget?.value || null;
            }
            if (!groupLabel) continue;

            // Find the host widget on the SubgraphNode for this promoted input.
            // ComfyUI stores it as input._widget (set in SubgraphNode._setWidget).
            // Fall back to a widgetId match, then to a name match.
            let hostWidget = input._widget;
            if (!hostWidget && input.widgetId) {
                hostWidget = subgraphNode.widgets?.find(w => w.widgetId === input.widgetId);
            }
            if (!hostWidget) {
                hostWidget = subgraphNode.widgets?.find(w => w.name === input.name);
            }
            if (!hostWidget) continue;

            // Set the label on the host widget. For store-backed projections
            // (the _projectPromotedWidget path) the `label` setter writes
            // through to the widget value store; for concrete widgets it sets
            // the property directly. Also keep input.label in sync so a future
            // re-resolution (_setWidget) picks up the corrected label.
            hostWidget.label = groupLabel;
            input.label = groupLabel;
        }
    } catch (e) {
        console.warn("[Holaf] holafUpdatePromotedLabels error:", e);
    }
}

// Separate extension: wrap onWidgetChanged on every SubgraphNode instance so
// promoted widget toggles are forwarded to the interior Holaf nodes.
app.registerExtension({
    name: "holaf.SubgraphWatcher",

    nodeCreated(node) {
        if (!node.isSubgraphNode || !node.isSubgraphNode()) return;

        const original = node.onWidgetChanged;
        node.onWidgetChanged = function (name, value, oldValue, widget) {
            if (original) original.call(this, name, value, oldValue, widget);
            try {
                holafHandlePromotedChange(this, name, value);
            } catch (e) {
                console.warn("[Holaf] SubgraphWidgetChange handler error:", e);
            }
        };

        // Fix promoted Holaf widget labels (group_name instead of "active").
        // Interior nodes may not be resolved yet at nodeCreated time, so retry
        // after the current tick.
        try {
            holafUpdatePromotedLabels(node);
            setTimeout(() => holafUpdatePromotedLabels(node), 0);
        } catch (e) {
            console.warn("[Holaf] SubgraphWatcher label init error:", e);
        }

        // Refresh labels after a graph load/configure cycle: interior nodes
        // are reconstructed during configure and may only be ready afterwards.
        const originalConfigure = node.onConfigure;
        node.onConfigure = function (o) {
            if (originalConfigure) originalConfigure.call(this, o);
            try {
                holafUpdatePromotedLabels(this);
                setTimeout(() => holafUpdatePromotedLabels(this), 0);
            } catch (e) {
                console.warn("[Holaf] SubgraphWatcher onConfigure label error:", e);
            }
        };
    }
});