/*
 * Copyright (C) 2025 Holaf
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program. If not, see <https://www.gnu.org/licenses/>.
 */

import { app } from "../../scripts/app.js";

// Base class for custom widgets
class HolafBaseWidget {
    constructor(name) {
        this.name = name;
        this.options = { serialize: false };
        this.type = "custom";
        this.y = 0;
        this.last_y = 0;
    }
    draw(ctx, node, width, posY, height) { }
    computeSize(width) { return [width, LiteGraph.NODE_WIDGET_HEIGHT]; }
    mouse(event, pos, node) { return false; }
    serializeValue(node, index) { return this.value; }
}


class RegionalPrompterWidget extends HolafBaseWidget {
    constructor(name, node) {
        super(name);
        this.node = node;
        // Find the 'zones' widget and parse its initial value
        const zonesWidget = node.widgets.find(w => w.name === "zones");
        this.value = this.parseValue(zonesWidget ? zonesWidget.value : '[]');

        // --- Default state for the 3 zones ---
        this.colors = ["rgba(255, 0, 0, 0.5)", "rgba(0, 255, 0, 0.5)", "rgba(0, 0, 255, 0.5)"];
        this.borderColors = ["#FF0000", "#00FF00", "#0000FF"];
        this.value.forEach((zone, i) => {
            zone.color = this.colors[i];
            zone.borderColor = this.borderColors[i];
        });

        this.selectedZone = null;
        this.interaction = { type: null, zone: null, startPos: null, startRect: null }; // type: 'drag' or 'resize'
        this.RESIZE_HANDLE_SIZE = 8;
    }

    parseValue(value) {
        try {
            if (typeof value === 'string') {
                return JSON.parse(value);
            }
            return value;
        } catch (e) {
            console.error("[HolafRegionalPrompter] Error parsing zone data:", e);
            return [];
        }
    }

    draw(ctx, node, widgetWidth, y, widgetHeight) {
        const width = node.widgets.find(w=>w.name==='width').value;
        const height = node.widgets.find(w=>w.name==='height').value;
        const aspectRatio = width > 0 && height > 0 ? width / height : 1;
        
        let displayHeight = node.size[1] - y - 10;
        let displayWidth = displayHeight * aspectRatio;
        if (displayWidth > node.size[0] - 20) {
            displayWidth = node.size[0] - 20;
            displayHeight = displayWidth / aspectRatio;
        }
        const offsetX = (node.size[0] - displayWidth) / 2;
        const offsetY = y + (node.size[1] - y - 10 - displayHeight) / 2;

        this.displayRect = { x: offsetX, y: offsetY, width: displayWidth, height: displayHeight };

        ctx.fillStyle = "#222";
        ctx.fillRect(offsetX, offsetY, displayWidth, displayHeight);
        ctx.strokeStyle = "#555";
        ctx.strokeRect(offsetX, offsetY, displayWidth, displayHeight);

        this.value.forEach(zone => {
            const rectX = offsetX + (zone.x / width) * displayWidth;
            const rectY = offsetY + (zone.y / height) * displayHeight;
            const rectW = (zone.width / width) * displayWidth;
            const rectH = (zone.height / height) * displayHeight;

            ctx.fillStyle = zone.color;
            ctx.fillRect(rectX, rectY, rectW, rectH);

            if (zone === this.selectedZone) {
                ctx.strokeStyle = zone.borderColor;
                ctx.lineWidth = 2;
                ctx.strokeRect(rectX, rectY, rectW, rectH);

                ctx.fillStyle = "#FFFFFF";
                ctx.fillRect(rectX + rectW - this.RESIZE_HANDLE_SIZE / 2, rectY + rectH - this.RESIZE_HANDLE_SIZE / 2, this.RESIZE_HANDLE_SIZE, this.RESIZE_HANDLE_SIZE);
            }
        });
        ctx.lineWidth = 1;
    }

    mouse(event, pos, node) {
        if (event.type === "mousedown") {
            return this.onMouseDown(event, pos, node);
        } else if (event.type === "mousemove") {
            return this.onMouseMove(event, pos, node);
        } else if (event.type === "mouseup") {
            return this.onMouseUp(event, pos, node);
        }
        return false;
    }

    onMouseDown(event, pos, node) {
        const x = pos[0];
        const y = pos[1];

        for (let i = this.value.length - 1; i >= 0; i--) {
            const zone = this.value[i];
            const width = node.widgets.find(w=>w.name==='width').value;
            const height = node.widgets.find(w=>w.name==='height').value;
            const rectX = this.displayRect.x + (zone.x / width) * this.displayRect.width;
            const rectY = this.displayRect.y + (zone.y / height) * this.displayRect.height;
            const rectW = (zone.width / width) * this.displayRect.width;
            const rectH = (zone.height / height) * this.displayRect.height;

            const handleX = rectX + rectW - this.RESIZE_HANDLE_SIZE;
            const handleY = rectY + rectH - this.RESIZE_HANDLE_SIZE;
            if (this.selectedZone === zone && x >= handleX && x <= handleX + this.RESIZE_HANDLE_SIZE && y >= handleY && y <= handleY + this.RESIZE_HANDLE_SIZE) {
                this.interaction = { type: 'resize', zone: zone, startPos: [...pos], startRect: { ...zone } };
                node.setDirtyCanvas(true, true);
                return true;
            }

            if (x >= rectX && x <= rectX + rectW && y >= rectY && y <= rectY + rectH) {
                this.interaction = { type: 'drag', zone: zone, startPos: [...pos], startRect: { ...zone } };
                this.selectedZone = zone;
                node.setDirtyCanvas(true, true);
                return true;
            }
        }

        this.selectedZone = null;
        this.interaction.type = null;
        node.setDirtyCanvas(true, true);
        return false;
    }

    onMouseMove(event, pos, node) {
        if (!this.interaction.type) return false;

        const dx = pos[0] - this.interaction.startPos[0];
        const dy = pos[1] - this.interaction.startPos[1];

        const realWidth = node.widgets.find(w=>w.name==='width').value;
        const realHeight = node.widgets.find(w=>w.name==='height').value;

        const dx_real = (dx / this.displayRect.width) * realWidth;
        const dy_real = (dy / this.displayRect.height) * realHeight;

        const zone = this.interaction.zone;
        const startRect = this.interaction.startRect;

        if (this.interaction.type === 'drag') {
            zone.x = Math.max(0, Math.min(realWidth - startRect.width, startRect.x + dx_real));
            zone.y = Math.max(0, Math.min(realHeight - startRect.height, startRect.y + dy_real));
        } else if (this.interaction.type === 'resize') {
            zone.width = Math.max(32, Math.min(realWidth - zone.x, startRect.width + dx_real));
            zone.height = Math.max(32, Math.min(realHeight - zone.y, startRect.height + dy_real));
        }

        this.updateNodeValue();
        node.setDirtyCanvas(true, true);
        return true;
    }

    onMouseUp(event, pos, node) {
        if (this.interaction.type) {
            this.interaction.type = null;
            return true;
        }
        return false;
    }

    updateNodeValue() {
        const zonesWidget = this.node.widgets.find(w => w.name === 'zones');
        if (zonesWidget) {
            zonesWidget.value = JSON.stringify(this.value.map(z => ({x: Math.round(z.x), y: Math.round(z.y), width: Math.round(z.width), height: Math.round(z.height)})));
        }
    }

    computeSize(width) {
        return [width, 256];
    }
}

app.registerExtension({
    name: "Holaf.RegionalPrompter",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === 'HolafRegionalPrompter') {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                onNodeCreated?.apply(this, arguments);
                this.addCustomWidget(new RegionalPrompterWidget("regional_prompter_widget", this));
            };

            Object.defineProperty(nodeType.prototype, "resizable", {
                get: function() { return true; },
                set: function() {}
            });
        }
    },
});
