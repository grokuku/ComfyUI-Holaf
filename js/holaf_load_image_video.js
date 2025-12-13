import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Holaf.LoadImageVideo.UploadFix",
    async nodeCreated(node) {
        if (node.comfyClass === "HolafLoadImageVideo") {
            // On cherche le widget qui contient le bouton upload
            const widget = node.widgets.find(w => w.name === "media_file");
            
            if (widget) {
                // Modification du label pour la clarté
                widget.label = "Media (Img/Vid)";
                
                // Hack pour modifier l'attribut 'accept' de l'input file créé par ComfyUI
                // ComfyUI crée un input file caché dynamiquement quand on clique.
                // On va surcharger la méthode d'ouverture de fichier du widget si elle existe,
                // ou tenter d'intercepter l'élément.
                
                // Méthode la plus stable pour les versions actuelles de ComfyUI :
                // On remplace le 'type' du widget pour tromper le frontend (partiellement)
                // ou on injecte un comportement personnalisé.
                
                const originalCallback = widget.callback;
                
                // On observe le DOM pour attraper l'input file quand il est créé
                // C'est une méthode avancée mais nécessaire pour changer le filtre "Image" par défaut.
                // Note : ComfyUI ne stocke pas l'input file de manière persistante.
                
                // Approche alternative : On modifie la propriété qui définit les extensions
                // Si le widget est de type "combo" (dropdown), il n'a pas de propriété file directe.
                // Mais le bouton upload à côté, si.
                
                // Pour faire simple et robuste sans casser le code de Comfy :
                // On va juste ajouter un écouteur global temporaire.
                
                // Note : La solution native parfaite nécessiterait de redéfinir le widget complet,
                // ce qui est lourd.
                
                // Solution pragmatique : Le code Python renvoie maintenant TOUS les fichiers.
                // L'utilisateur peut les voir dans la liste.
                // Pour l'upload, on va essayer de changer l'attribut accept à la volée.
                
                // Cette partie est purement indicative : si ComfyUI change son code interne,
                // le filtre reviendra à "Image". Mais la node Python, elle, acceptera tout.
                try {
                     // Recherche proactive d'inputs existants (rare)
                } catch (e) {
                    console.error("Holaf Upload Fix Error", e);
                }
            }
        }
    }
});

// Extension globale pour modifier le comportement des inputs file créés pour cette node spécifique
// On utilise un MutationObserver pour détecter quand ComfyUI ouvre la fenêtre de dialogue (crée un input file)
const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
            if (node.tagName === 'INPUT' && node.type === 'file') {
                // On vérifie si c'est pour notre node (difficile à tracer directement)
                // Mais on peut autoriser globalement video/* pour être large
                if (node.accept && node.accept.includes("image/")) {
                    // On élargit le filtre
                    node.accept = "image/*,video/*,.mp4,.mkv,.webm,.mov,.avi,.gif,.webp";
                }
            }
        }
    }
});

observer.observe(document.body, { childList: true, subtree: true });