import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Holaf.LoadImageVideo.UploadFix",
    async nodeCreated(node) {
        if (node.comfyClass === "HolafLoadImageVideo") {
            // On cherche le widget d'upload (qui est souvent le premier widget 'image')
            const widget = node.widgets.find(w => w.name === "media_file");
            
            if (widget && widget.element) {
                // Modification cosmetique du label si besoin
                // Mais surtout, on essaie d'intercepter la création de l'input file si possible
                // Note : ComfyUI crée l'input file dynamiquement, c'est difficile à patcher proprement
                // sans modifier le core.
                
                // Solution de contournement UX :
                // On ajoute un tooltip explicite sur le widget
                widget.inputEl.title = "Select Images or Videos (All Files)";
            }
        }
    }
});