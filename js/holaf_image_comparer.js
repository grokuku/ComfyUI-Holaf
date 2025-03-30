// Combined JavaScript for holaf-comfy
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";
import { ComfyWidgets } from "../../scripts/widgets.js"; // Needed by HolafBaseServerNode

// --- Minimal defineProperty (recreated from shared_utils) ---
// Helper to ensure properties can be redefined if they exist and are configurable.
function defineProperty(instance, property, desc) {
    var _a, _b, _c, _d, _e, _f;
    const existingDesc = Object.getOwnPropertyDescriptor(instance, property);
    // Check if property exists and is not configurable
    if ((existingDesc === null || existingDesc === void 0 ? void 0 : existingDesc.configurable) === false) {
        // Optionally log or throw error, or just skip redefinition
        console.warn(`[holaf] Cannot redefine non-configurable property "${property}"`);
        return; // Skip redefinition
        // OR: throw new Error(`Error: holaf-comfy cannot define un-configurable property "${property}"`);
    }
    // Merge getter/setter if both exist (simple merge, might need adjustment based on original logic)
    if ((existingDesc === null || existingDesc === void 0 ? void 0 : existingDesc.get) && desc.get) {
        const originalGet = existingDesc.get;
        const newGet = desc.get;
        desc.get = function() {
            originalGet.apply(this, []); // Call original getter (might have side effects)
            return newGet.apply(this, []); // Call new getter
        };
    }
    if ((existingDesc === null || existingDesc === void 0 ? void 0 : existingDesc.set) && desc.set) {
        const originalSet = existingDesc.set;
        const newSet = desc.set;
        desc.set = function(v) {
            originalSet.apply(this, [v]); // Call original setter
            newSet.apply(this, [v]); // Call new setter
        };
    }
    // Ensure descriptor properties are set, defaulting to existing or standard values
    desc.enumerable = (_b = (_a = desc.enumerable) !== null && _a !== void 0 ? _a : existingDesc === null || existingDesc === void 0 ? void 0 : existingDesc.enumerable) !== null && _b !== void 0 ? _b : true;
    desc.configurable = (_d = (_c = desc.configurable) !== null && _c !== void 0 ? _c : existingDesc === null || existingDesc === void 0 ? void 0 : existingDesc.configurable) !== null && _d !== void 0 ? _d : true;
    // Set writable only if it's a data descriptor (no get/set)
    if (!desc.get && !desc.set) {
        desc.writable = (_f = (_e = desc.writable) !== null && _e !== void 0 ? _e : existingDesc === null || existingDesc === void 0 ? void 0 : existingDesc.writable) !== null && _f !== void 0 ? _f : true;
    }
    return Object.defineProperty(instance, property, desc);
}


// --- Logging Setup ---
var LogLevel;
(function (LogLevel) {
    LogLevel[LogLevel["ERROR"] = 2] = "ERROR";
    LogLevel[LogLevel["WARN"] = 3] = "WARN";
    LogLevel[LogLevel["INFO"] = 4] = "INFO";
    LogLevel[LogLevel["DEV"] = 6] = "DEV"; // Added DEV level for base node logging
})(LogLevel || (LogLevel = {}));

const LogLevelToMethod = {
    [LogLevel.ERROR]: "error",
    [LogLevel.WARN]: "warn",
    [LogLevel.INFO]: "info",
    [LogLevel.DEV]: "log", // Map DEV to console.log
};

let GLOBAL_LOG_LEVEL = LogLevel.WARN; // Default to WARN

class Logger {
    log(level, message, ...args) {
        var _a;
        if (level <= GLOBAL_LOG_LEVEL) {
            const method = LogLevelToMethod[level] || "log";
            (_a = console[method]) === null || _a === void 0 ? void 0 : _a.call(console, `[holaf] ${message}`, ...args);
        }
    }
     logParts(level, message, ...args) { // Keep logParts for base_node compatibility
        if (level <= GLOBAL_LOG_LEVEL) {
            const method = LogLevelToMethod[level] || "log";
            const prefix = '[holaf] '; // Simplified prefix
            // Basic formatting, no CSS for simplicity in combined file
            return [method, [prefix + message, ...args]];
        }
        return ["none", []];
    }
}
const logger = new Logger(); // Global logger instance


// --- Canvas Utilities (from utils_canvas.js) ---
function binarySearch(max, getValue, match) {
    let min = 0;
    while (min <= max) {
        let guess = Math.floor((min + max) / 2);
        const compareVal = getValue(guess);
        if (compareVal === match)
            return guess;
        if (compareVal < match)
            min = guess + 1;
        else
            max = guess - 1;
    }
    return max;
}

function fitString(ctx, str, maxWidth) {
    let width = ctx.measureText(str).width;
    const ellipsis = "…";
    const ellipsisWidth = measureText(ctx, ellipsis);
    if (width <= maxWidth || width <= ellipsisWidth) {
        return str;
    }
    const index = binarySearch(str.length, (guess) => measureText(ctx, str.substring(0, guess)), maxWidth - ellipsisWidth);
    return str.substring(0, index) + ellipsis;
}

function measureText(ctx, str) {
    return ctx.measureText(str).width;
}

function isLowQuality() {
    var _a;
    const canvas = app.canvas;
    return (((_a = canvas.ds) === null || _a === void 0 ? void 0 : _a.scale) || 1) <= 0.5;
}

function drawNodeWidget(ctx, options) {
    const lowQuality = isLowQuality();
    const data = {
        width: options.width,
        height: options.height,
        posY: options.posY,
        lowQuality,
        margin: 15,
        colorOutline: LiteGraph.WIDGET_OUTLINE_COLOR,
        colorBackground: LiteGraph.WIDGET_BGCOLOR,
        colorText: LiteGraph.WIDGET_TEXT_COLOR,
        colorTextSecondary: LiteGraph.WIDGET_SECONDARY_TEXT_COLOR,
    };
    ctx.strokeStyle = options.colorStroke || data.colorOutline;
    ctx.fillStyle = options.colorBackground || data.colorBackground;
    ctx.beginPath();
    ctx.roundRect(data.margin, data.posY, data.width - data.margin * 2, data.height, lowQuality ? [0] : options.borderRadius ? [options.borderRadius] : [options.height * 0.5]);
    ctx.fill();
    if (!lowQuality) {
        ctx.stroke();
    }
    return data;
}

function drawRoundedRectangle(ctx, options) {
    const lowQuality = isLowQuality();
    options = { ...options };
    ctx.strokeStyle = options.colorStroke || LiteGraph.WIDGET_OUTLINE_COLOR;
    ctx.fillStyle = options.colorBackground || LiteGraph.WIDGET_BGCOLOR;
    ctx.beginPath();
    ctx.roundRect(options.posX, options.posY, options.width, options.height, lowQuality ? [0] : options.borderRadius ? [options.borderRadius] : [options.height * 0.5]);
    ctx.fill();
    !lowQuality && ctx.stroke();
}

// drawNumberWidgetPart, drawTogglePart, drawInfoIcon are likely unused by image comparer, omitted for brevity


// --- Base Widget (from utils_widgets.js) ---
class HolafBaseWidget {
    constructor(name) {
        this.name = name;
        // FIX: Do not assign this.value here to prevent premature setter call in subclass
        // this.value = null;
        this.options = { serialize: false };
        this.type = "custom";
        // Add properties expected by HolafImageComparerWidget if any were missed
        this.y = 0; // Seems needed by HolafImageComparerWidget draw logic
        this.last_y = 0; // Seems needed by HolafImageComparerWidget draw logic
    }
    draw(ctx, node, width, posY, height) { }
    computeSize(width) { return [width, LiteGraph.NODE_WIDGET_HEIGHT]; }
    mouse(event, pos, node) { return false; }
    serializeValue(node, index) { return this.value; }
}


// --- Base Node (from base_node.js) ---
const OVERRIDDEN_SERVER_NODES = new Map(); // Keep this global for the override logic

class HolafBaseNode extends LGraphNode {
    constructor(title = HolafBaseNode.title, skipOnConstructedCall = true) {
        super(title);
        this.comfyClass = "__NEED_COMFY_CLASS__";
        this.nickname = "holaf";
        this.isVirtualNode = false;
        this.isDropEnabled = false; // Disabled drag/drop features
        this.removed = false;
        this.configuring = false;
        this._tempWidth = 0;
        this.__constructed__ = false;
        // Removed helpDialog initialization

        if (title == "__NEED_CLASS_TITLE__") { throw new Error("HolafBaseNode needs overrides."); }
        this.widgets = this.widgets || [];
        this.properties = this.properties || {};

        setTimeout(() => {
            if (this.comfyClass == "__NEED_COMFY_CLASS__") { throw new Error("HolafBaseNode needs a comfy class override."); }
            if (this.constructor.type == "__NEED_CLASS_TYPE__") { throw new Error("HolafBaseNode needs overrides."); }
            this.checkAndRunOnConstructed();
        });

        // Keep mode property definition if needed, otherwise remove
        defineProperty(this, "mode", {
            get: () => { return this.rgthree_mode; /* TODO: Rename this internal property? */ },
            set: (mode) => {
                if (this.rgthree_mode != mode) {
                    const oldMode = this.rgthree_mode;
                    this.rgthree_mode = mode;
                    this.onModeChange(oldMode, mode);
                }
            },
        });
    }

    checkAndRunOnConstructed() {
        var _a;
        if (!this.__constructed__) {
            this.onConstructed();
            // Use the global logger instance
            const [n, v] = logger.logParts(LogLevel.DEV, `[HolafBaseNode] Child class did not call onConstructed for "${this.type}.`);
            (_a = console[n]) === null || _a === void 0 ? void 0 : _a.call(console, ...v);
        }
        return this.__constructed__;
    }

    onConstructed() {
        var _a;
        if (this.__constructed__) return false;
        this.type = (_a = this.type) !== null && _a !== void 0 ? _a : undefined;
        this.__constructed__ = true;
        // Simplified - invokeExtensionsAsync was removed
        return this.__constructed__;
    }

    configure(info) {
        this.configuring = true;
        super.configure(info);
        for (const w of this.widgets || []) { w.last_y = w.last_y || 0; }
        this.configuring = false;
    }

    clone() {
        const cloned = super.clone();
        if ((cloned === null || cloned === void 0 ? void 0 : cloned.properties) && !!window.structuredClone) {
            cloned.properties = structuredClone(cloned.properties);
        }
        return cloned;
    }

    onModeChange(from, to) { }
    async handleAction(action) { action; } // No-op

    removeWidget(widgetOrSlot) {
        if (!this.widgets) { return; }
        if (typeof widgetOrSlot === "number") { this.widgets.splice(widgetOrSlot, 1); }
        else if (widgetOrSlot) {
            const index = this.widgets.indexOf(widgetOrSlot);
            if (index > -1) { this.widgets.splice(index, 1); }
        }
    }

    defaultGetSlotMenuOptions(slot) {
         var _a, _b;
        const menu_info = [];
        if ((_b = (_a = slot === null || slot === void 0 ? void 0 : slot.output) === null || _a === void 0 ? void 0 : _a.links) === null || _b === void 0 ? void 0 : _b.length) {
            menu_info.push({ content: "Disconnect Links", slot });
        }
        let inputOrOutput = slot.input || slot.output;
        if (inputOrOutput) {
            if (inputOrOutput.removable) {
                menu_info.push(inputOrOutput.locked ? { content: "Cannot remove" } : { content: "Remove Slot", slot });
            }
            if (!inputOrOutput.nameLocked) {
                menu_info.push({ content: "Rename Slot", slot });
            }
        }
        return menu_info;
    }

    onRemoved() {
        var _a;
        (_a = super.onRemoved) === null || _a === void 0 ? void 0 : _a.call(this);
        this.removed = true;
    }

    static setUp(...args) { }
    getHelp() { return ""; }

    getExtraMenuOptions(canvas, options) {
        var _a, _b, _c, _d, _e, _f;
         if (super.getExtraMenuOptions) {
            (_a = super.getExtraMenuOptions) === null || _a === void 0 ? void 0 : _a.apply(this, [canvas, options]);
        } else if ((_c = (_b = this.constructor.nodeType) === null || _b === void 0 ? void 0 : _b.prototype) === null || _c === void 0 ? void 0 : _c.getExtraMenuOptions) {
            (_f = (_e = (_d = this.constructor.nodeType) === null || _d === void 0 ? void 0 : _d.prototype) === null || _e === void 0 ? void 0 : _e.getExtraMenuOptions) === null || _f === void 0 ? void 0 : _f.apply(this, [canvas, options]);
        }
        // Removed help menu item addition
        return options;
    }
}
HolafBaseNode.exposedActions = [];
HolafBaseNode.title = "__NEED_CLASS_TITLE__";
HolafBaseNode.type = "__NEED_CLASS_TYPE__";
HolafBaseNode.category = "holaf";
HolafBaseNode._category = "holaf";

// HolafBaseVirtualNode might be unused now, but keep for structure if needed later
class HolafBaseVirtualNode extends HolafBaseNode {
    constructor(title = HolafBaseNode.title) {
        super(title, false);
        this.isVirtualNode = true;
    }
    static setUp() {
        if (!this.type) { throw new Error(`Missing type for HolafBaseVirtualNode: ${this.title}`); }
        LiteGraph.registerNodeType(this.type, this);
        if (this._category) { this.category = this._category; }
    }
}

class HolafBaseServerNode extends HolafBaseNode {
    constructor(title) {
        super(title, true);
        this.isDropEnabled = false; // Disable drop by default in simplified version
        this.serialize_widgets = true;
        this.setupFromServerNodeData(); // Call setup
        this.onConstructed(); // Ensure base onConstructed is called
    }

    getWidgets() { return ComfyWidgets; }

    async setupFromServerNodeData() {
        var _a, _b, _c, _d, _e;
        const nodeData = this.constructor.nodeData;
        if (!nodeData) { throw Error("No node data"); }
        this.comfyClass = nodeData.name;
        let inputs = nodeData["input"]["required"];
        if (nodeData["input"]["optional"] != undefined) {
            inputs = Object.assign({}, inputs, nodeData["input"]["optional"]);
        }
        const WIDGETS = this.getWidgets();
        const config = { minWidth: 1, minHeight: 1, widget: null };

        for (const inputName in inputs) {
            const inputData = inputs[inputName];
            const type = inputData[0];
            // Simplified widget creation logic - check if PreviewImage handles this
             if ((_a = inputData[1]) === null || _a === void 0 ? void 0 : _a.forceInput) {
                 this.addInput(inputName, type);
             } else {
                 // Assume PreviewImage or core handles widget creation for IMAGE inputs
                 // Add input only if no widget is implicitly created by the type
                 // This might need adjustment based on how PreviewImage works
                 if (type !== "IMAGE" && type !== "MASK") { // Common types handled by PreviewImage?
                    let widgetCreated = true;
                    if (Array.isArray(type)) { Object.assign(config, WIDGETS.COMBO(this, inputName, inputData, app) || {}); }
                    else if (`${type}:${inputName}` in WIDGETS) { Object.assign(config, WIDGETS[`${type}:${inputName}`](this, inputName, inputData, app) || {}); }
                    else if (type in WIDGETS) { Object.assign(config, WIDGETS[type](this, inputName, inputData, app) || {}); }
                    else { this.addInput(inputName, type); widgetCreated = false; }

                    // Keep forceInput/defaultInput options if widget was created
                    if (widgetCreated && ((_b = inputData[1]) === null || _b === void 0 ? void 0 : _b.forceInput) && (config === null || config === void 0 ? void 0 : config.widget)) {
                        if (!config.widget.options) config.widget.options = {};
                        config.widget.options.forceInput = inputData[1].forceInput;
                    }
                    if (widgetCreated && ((_c = inputData[1]) === null || _c === void 0 ? void 0 : _c.defaultInput) && (config === null || config === void 0 ? void 0 : config.widget)) {
                        if (!config.widget.options) config.widget.options = {};
                        config.widget.options.defaultInput = inputData[1].defaultInput;
                    }
                 } else {
                     // Add inputs for types potentially handled by PreviewImage base
                     this.addInput(inputName, type);
                 }
             }
        }
        for (const o in nodeData["output"]) {
            let output = nodeData["output"][o];
            if (output instanceof Array) output = "COMBO"; // Keep COMBO handling
            const outputName = nodeData["output_name"][o] || output;
            const outputShape = nodeData["output_is_list"][o] ? LiteGraph.GRID_SHAPE : LiteGraph.CIRCLE_SHAPE;
            this.addOutput(outputName, output, { shape: outputShape });
        }
        const s = this.computeSize();
        s[0] = Math.max((_d = config.minWidth) !== null && _d !== void 0 ? _d : 1, s[0] * 1.5);
        s[1] = Math.max((_e = config.minHeight) !== null && _e !== void 0 ? _e : 1, s[1]);
        this.size = s;
        this.serialize_widgets = true;
    }

    static registerForOverride(comfyClass, nodeData, holafClass) {
        if (OVERRIDDEN_SERVER_NODES.has(comfyClass)) { throw Error(`Already have a class to override ${comfyClass.type || comfyClass.name || comfyClass.title}`); }
        OVERRIDDEN_SERVER_NODES.set(comfyClass, holafClass);
        if (!holafClass.__registeredForOverride__) {
            holafClass.__registeredForOverride__ = true;
            holafClass.nodeType = comfyClass;
            holafClass.nodeData = nodeData;
            holafClass.onRegisteredForOverride(comfyClass, holafClass);
        }
    }
    static onRegisteredForOverride(comfyClass, holafClass) { }
}
HolafBaseServerNode.nodeType = null;
HolafBaseServerNode.nodeData = null;
HolafBaseServerNode.__registeredForOverride__ = false;


// --- Image Comparer Widget (from image_comparer.js) ---
class HolafImageComparerWidget extends HolafBaseWidget {
     constructor(name, node) {
        super(name);
        this.hitAreas = {};
        this.selected = [];
        this._value = { images: [] }; // Initialize _value here
        this.node = node;
    }

    set value(v) {
        let cleanedVal;
        // FIX: Add null/undefined check for v
        if (!v) {
            cleanedVal = []; // Default to empty array if v is null/undefined
        } else if (Array.isArray(v)) {
            cleanedVal = v.map((d, i) => {
                if (!d || typeof d === "string") {
                    d = { url: d, name: i == 0 ? "A" : "B", selected: true };
                }
                return d;
            });
        } else {
            // Now it's safe to access v.images if v is an object
            cleanedVal = v.images || [];
        }
        if (cleanedVal.length > 2) {
            const hasAAndB = cleanedVal.some((i) => i.name.startsWith("A")) &&
                cleanedVal.some((i) => i.name.startsWith("B"));
            if (!hasAAndB) { cleanedVal = [cleanedVal[0], cleanedVal[1]]; }
        }
        let selected = cleanedVal.filter((d) => d.selected);
        if (!selected.length && cleanedVal.length) { cleanedVal[0].selected = true; }
        selected = cleanedVal.filter((d) => d.selected);
        if (selected.length === 1 && cleanedVal.length > 1) {
            const firstNonSelected = cleanedVal.find((d) => !d.selected);
            if (firstNonSelected) { firstNonSelected.selected = true; }
        }
        // FIX: Ensure this._value exists before assigning to its property
        if (!this._value) {
          this._value = { images: [] }; // Initialize if it doesn't exist (redundant due to constructor init, but safe)
        }
        this._value.images = cleanedVal;
        selected = cleanedVal.filter((d) => d.selected);
        this.setSelected(selected);
    }

    get value() { return this._value; }

    setSelected(selected) {
        // Ensure _value exists (might be redundant if constructor always runs first, but safe)
        if (!this._value) { this._value = { images: [] }; }
        this._value.images.forEach((d) => (d.selected = false));

        // FIX: Check if this.node exists AND this.node.imgs is an array before accessing its properties
        const nodeImgs = []; // Create temporary array
        if (this.node) {
            // Ensure this.node.imgs is initialized as an array if it doesn't exist
            if (!Array.isArray(this.node.imgs)) {
                this.node.imgs = [];
            }
            // Now safe to clear and push
            // this.node.imgs.length = 0; // Clear previous images - MOVED below loop

            for (const sel of selected) {
                if (sel) {
                    if (!sel.img) {
                        sel.img = new Image();
                        sel.img.src = sel.url;
                    }
                    sel.selected = true;
                    nodeImgs.push(sel.img); // Add the image object to temp array
                }
            }
            this.node.imgs = nodeImgs; // Assign the collected images to the node
        }
        this.selected = selected.slice(0, 2);
        while (this.selected.length < 2) { this.selected.push(null); }
    }

    draw(ctx, node, width, y) {
        var _a;
        this.hitAreas = {};
        // Ensure this.value exists before accessing length
        if (this.value && this.value.images.length > 2) {
            ctx.save();
            ctx.textAlign = "left";
            ctx.textBaseline = "top";
            ctx.font = `14px Arial`;
            const drawData = [];
            const spacing = 5;
            let currentX = 0;
            for (const img of this.value.images) {
                const textWidth = measureText(ctx, img.name);
                drawData.push({ img, text: img.name, x: currentX, width: textWidth });
                currentX += textWidth + spacing;
            }
            const totalWidth = currentX - spacing;
            let startX = (node.size[0] - totalWidth) / 2;
            for (const d of drawData) {
                ctx.fillStyle = d.img.selected ? "rgba(180, 180, 180, 1)" : "rgba(180, 180, 180, 0.5)";
                ctx.fillText(d.text, startX + d.x, y);
                this.hitAreas[d.text] = {
                    bounds: [startX + d.x, y, d.width, 14],
                    data: d.img,
                    onDown: (event, pos, node, part) => this.onSelectionDown(event, pos, node, part),
                };
            }
            ctx.restore();
            y += 20;
        }
        if (((_a = node.properties) === null || _a === void 0 ? void 0 : _a["comparer_mode"]) === "Click") {
            this.drawImage(ctx, this.selected[this.node.isPointerDown ? 1 : 0], y);
        } else {
            this.drawImage(ctx, this.selected[0], y);
            if (node.isPointerOver && this.selected[1]) {
                this.drawImage(ctx, this.selected[1], y, this.node.pointerOverPos[0]);
            }
        }
    }

    onSelectionDown(event, pos, node, part) {
        const selected = [...this.selected];
        const clickedData = part.data;
        if (clickedData.name.startsWith("A")) { selected[0] = clickedData; }
        else if (clickedData.name.startsWith("B")) { selected[1] = clickedData; }
        else { // Fallback logic
            if (clickedData.name.startsWith("A")) { selected[0] = clickedData; }
            else { selected[1] = clickedData; }
        }
        // Ensure only two are selected (simplified logic)
        let currentSelected = selected.filter(s => s && s.selected);
         if (currentSelected.length > 2) {
             if (selected[0] === clickedData && selected[1] && selected[1] !== clickedData) { /* Keep selected[1] */ }
             else if (selected[1] === clickedData && selected[0] && selected[0] !== clickedData) { /* Keep selected[0] */ }
             else {
                 const otherSelected = this._value.images.find(img => img.selected && img !== clickedData);
                 if (clickedData.name.startsWith("A")) {
                     selected[1] = otherSelected || this._value.images.find(img => !img.selected && img.name.startsWith("B")) || this._value.images.find(img => !img.selected);
                 } else {
                     selected[0] = otherSelected || this._value.images.find(img => !img.selected && img.name.startsWith("A")) || this._value.images.find(img => !img.selected);
                 }
             }
         }
        this.setSelected(selected);
        node.setDirtyCanvas(true, true);
    }

    drawImage(ctx, image, y, cropX) {
        var _a, _b;
        if (!image || !image.img || !image.img.naturalWidth || !image.img.naturalHeight) { return; }
        let [nodeWidth, nodeHeight] = this.node.size;
        const imageAspect = image.img.naturalWidth / image.img.naturalHeight;
        let availableHeight = nodeHeight - y;
        const widgetAspect = nodeWidth / availableHeight;
        let targetWidth, targetHeight, offsetX = 0;
        if (imageAspect > widgetAspect) {
            targetWidth = nodeWidth; targetHeight = targetWidth / imageAspect;
        } else {
            targetHeight = availableHeight; targetWidth = targetHeight * imageAspect; offsetX = (nodeWidth - targetWidth) / 2;
        }
        if (targetWidth <= 0 || targetHeight <= 0) return;
        const widthMultiplier = image.img.naturalWidth / targetWidth;
        const sourceX = 0, sourceY = 0;
        const sourceWidth = cropX != null ? Math.max(0, (cropX - offsetX) * widthMultiplier) : image.img.naturalWidth;
        const sourceHeight = image.img.naturalHeight;
        const destX = offsetX;
        const destY = y + (availableHeight - targetHeight) / 2;
        const destWidth = cropX != null ? Math.max(0, cropX - offsetX) : targetWidth;
        const destHeight = targetHeight;
        if (sourceWidth <= 0 || sourceHeight <= 0 || destWidth <= 0 || destHeight <= 0) return;
        ctx.save();
        ctx.beginPath();
        let globalCompositeOperation = ctx.globalCompositeOperation;
        if (cropX != null) {
            ctx.rect(destX, destY, destWidth, destHeight); ctx.clip();
        }
        ctx.drawImage(image.img, sourceX, sourceY, sourceWidth, sourceHeight, destX, destY, destWidth, destHeight);
        if (cropX != null && cropX >= destX && cropX <= destX + targetWidth) {
            ctx.beginPath(); ctx.moveTo(cropX, destY); ctx.lineTo(cropX, destY + destHeight);
            ctx.globalCompositeOperation = "difference"; ctx.strokeStyle = "rgba(255,255,255, 1)"; ctx.lineWidth = 1; ctx.stroke();
        }
        ctx.globalCompositeOperation = globalCompositeOperation;
        ctx.restore();
    }

    computeSize(width) {
        let height = 200;
        // Ensure this.value exists before accessing length
        if (this.value && this.value.images.length > 2) { height += 20; }
        return [width, height];
    }

    serializeValue(node, index) {
        const v = [];
        // Ensure this._value exists before accessing images
        for (const data of (this._value?.images || [])) {
             if (data) {
                const d = { ...data }; delete d.img; v.push(d);
            }
        }
        return { images: v };
    }
}


// --- Image Comparer Node (from image_comparer.js) ---
function imageDataToUrl(data) { // Keep this utility function local
    return api.apiURL(`/view?filename=${encodeURIComponent(data.filename)}&type=${data.type}&subfolder=${data.subfolder}${app.getPreviewFormatParam()}${app.getRandParam()}`);
}

class HolafImageComparer extends HolafBaseServerNode {
    constructor(title = HolafImageComparer.title) {
        super(title);
        this.imageIndex = 0;
        this.imgs = [];
        this.serialize_widgets = true;
        this.isPointerDown = false;
        this.isPointerOver = false;
        this.pointerOverPos = [0, 0];
        this.canvasWidget = null;
        this.properties["comparer_mode"] = "Slide";
    }

    onExecuted(output) {
        var _a;
        (_a = super.onExecuted) === null || _a === void 0 ? void 0 : _a.call(this, output);
        if ("images" in output) {
            this.canvasWidget.value = {
                images: (output.images || []).map((d, i) => ({ name: i === 0 ? "A" : "B", selected: true, url: imageDataToUrl(d) })),
            };
        } else {
            output.a_images = output.a_images || []; output.b_images = output.b_images || [];
            const imagesToChoose = [];
            const multiple = output.a_images.length + output.b_images.length > 2;
            for (const [i, d] of output.a_images.entries()) { imagesToChoose.push({ name: output.a_images.length > 1 || multiple ? `A${i + 1}` : "A", selected: i === 0, url: imageDataToUrl(d) }); }
            for (const [i, d] of output.b_images.entries()) { imagesToChoose.push({ name: output.b_images.length > 1 || multiple ? `B${i + 1}` : "B", selected: i === 0, url: imageDataToUrl(d) }); }
            this.canvasWidget.value = { images: imagesToChoose };
        }
    }

    onSerialize(serialised) {
        var _a;
        super.onSerialize && super.onSerialize(serialised);
        for (let [index, widget_value] of (serialised.widgets_values || []).entries()) {
            if (((_a = this.widgets[index]) === null || _a === void 0 ? void 0 : _a.name) === "holaf_comparer") {
                serialised.widgets_values[index] = this.widgets[index].value.images.map((d) => { d = { ...d }; delete d.img; return d; });
            }
        }
    }

    onNodeCreated() {
        this.canvasWidget = this.addCustomWidget(new HolafImageComparerWidget("holaf_comparer", this));
        this.setSize(this.computeSize());
        this.setDirtyCanvas(true, true);
    }

    setIsPointerDown(down = this.isPointerDown) {
        const newIsDown = down && !!app.canvas.pointer_is_down;
        if (this.isPointerDown !== newIsDown) { this.isPointerDown = newIsDown; this.setDirtyCanvas(true, false); }
        this.imageIndex = this.isPointerDown ? 1 : 0;
        if (this.isPointerDown) { requestAnimationFrame(() => { this.setIsPointerDown(); }); }
    }

    onMouseDown(event, pos, canvas) { var _a; (_a = super.onMouseDown) === null || _a === void 0 ? void 0 : _a.call(this, event, pos, canvas); this.setIsPointerDown(true); return false; }
    onMouseEnter(event) { var _a; (_a = super.onMouseEnter) === null || _a === void 0 ? void 0 : _a.call(this, event); this.setIsPointerDown(!!app.canvas.pointer_is_down); this.isPointerOver = true; }
    onMouseLeave(event) { var _a; (_a = super.onMouseLeave) === null || _a === void 0 ? void 0 : _a.call(this, event); this.setIsPointerDown(false); this.isPointerOver = false; }
    onMouseMove(event, pos, canvas) { var _a; (_a = super.onMouseMove) === null || _a === void 0 ? void 0 : _a.call(this, event, pos, canvas); this.pointerOverPos = [...pos]; this.imageIndex = this.pointerOverPos[0] > this.size[0] / 2 ? 1 : 0; }

    getHelp() { /* ... help text ... */ return ` ... help text ... `; } // Keep help text

    static setUp(comfyClass, nodeData) { HolafBaseServerNode.registerForOverride(comfyClass, nodeData, HolafImageComparer); }
    static onRegisteredForOverride(comfyClass) { setTimeout(() => { HolafImageComparer.category = comfyClass.category; }); }
}
HolafImageComparer.title = "test comparer"; // New Name
HolafImageComparer.type = "test comparer"; // New Name
HolafImageComparer.comfyClass = "test comparer"; // New Name
HolafImageComparer["@comparer_mode"] = { type: "combo", values: ["Slide", "Click"] };


// --- LiteGraph Node Type Override ---
const oldregisterNodeType = LiteGraph.registerNodeType;
LiteGraph.registerNodeType = async function (nodeId, baseClass) {
    var _a;
    const clazz = OVERRIDDEN_SERVER_NODES.get(baseClass) || baseClass;
    if (clazz !== baseClass) {
        const classLabel = clazz.type || clazz.name || clazz.title;
        // Use global logger
        const [n, v] = logger.logParts(LogLevel.DEBUG, `${nodeId}: replacing default ComfyNode implementation with custom ${classLabel} class.`);
        (_a = console[n]) === null || _a === void 0 ? void 0 : _a.call(console, ...v);
    }
    return oldregisterNodeType.call(LiteGraph, nodeId, clazz);
};


// --- Main Extension Setup (from original holaf.js) ---
const holaf = {
    name: "holaf.comfy",
    init() { logger.log(LogLevel.INFO, "Init"); },
    setup() { logger.log(LogLevel.INFO, "Setup"); },
    // Add other lifecycle methods if needed, e.g., loadedGraphNode
};

// --- Register Main Extension ---
app.registerExtension(holaf);
logger.log(LogLevel.INFO, "Holaf extension registered.");


// --- Register Node Override ---
app.registerExtension({
    name: "holaf.ImageComparer.Override", // Unique name for this registration part
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        // Use the correct type comparison from the node class static property
        if (nodeData.name === HolafImageComparer.type) { // Type check should still work
            HolafImageComparer.setUp(nodeType, nodeData); // Call the static setup
        }
    },
});

// Optional: Assign to window for debugging
window.holaf = holaf;
