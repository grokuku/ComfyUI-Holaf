import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Holaf.VerticalReroute",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "HolafVerticalReroute") {
            
            // 1. Force la taille par défaut à la création
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                if (onNodeCreated) onNodeCreated.apply(this, arguments);
                
                // Taille fixe verticale mince (Largeur: 40, Hauteur: 60)
                this.size = [40, 60];
                
                // Configuration des directions des Slots
                // Slot 0: Left, Slot 1: Top, Slot 2: Right
                if (this.inputs && this.inputs.length >= 3) {
                    this.inputs[0].dir = LiteGraph.LEFT;
                    this.inputs[1].dir = LiteGraph.UP;
                    this.inputs[2].dir = LiteGraph.RIGHT;
                    
                    // On nomme les slots pour le debug, mais on pourra les cacher visuellement plus tard
                    this.inputs[0].name = "";
                    this.inputs[1].name = "";
                    this.inputs[2].name = "";
                }

                // Configuration de la sortie vers le BAS
                if (this.outputs && this.outputs.length > 0) {
                    this.outputs[0].dir = LiteGraph.DOWN;
                    this.outputs[0].name = "";
                }
            };

            // 2. Hack: Centralisation des points de connexion (Le concept "Fantôme")
            // On force LiteGraph à croire que les 3 entrées sont au même endroit (Haut/Centre)
            const origGetConnectionPos = nodeType.prototype.getConnectionPos;
            nodeType.prototype.getConnectionPos = function(is_input, slot) {
                
                // Si c'est une entrée (peu importe laquelle des 3), on renvoie le point Haut-Centre
                if (is_input) {
                    // X = Position Node + Moitié Largeur
                    // Y = Position Node (Bord haut)
                    return [this.pos[0] + this.size[0] / 2, this.pos[1]];
                }
                
                // Si c'est la sortie, on renvoie le point Bas-Centre
                if (!is_input && slot === 0) {
                     return [this.pos[0] + this.size[0] / 2, this.pos[1] + this.size[1]];
                }

                // Fallback standard (ne devrait pas être atteint pour cette node)
                return origGetConnectionPos.apply(this, arguments);
            }
        }
    }
});