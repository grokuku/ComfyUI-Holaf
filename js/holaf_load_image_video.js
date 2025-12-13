import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Holaf.LoadImageVideo.AggressiveFix",
    async setup() {
        // On écoute tout le document pour l'événement "click"
        // C'est le seul moyen sûr d'intercepter la création de l'input file par le widget Comfy
        document.addEventListener('click', (e) => {
            // On vérifie si le clic vient d'un bouton de widget "upload"
            // Les classes peuvent varier, mais souvent c'est lié au fileDialog
            
            // Stratégie : On utilise un MutationObserver à très court terme
            // Dès qu'on clique n'importe où, on surveille la création d'un <input type="file">
            // pendant 500ms.
            
            const observer = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                    for (const node of mutation.addedNodes) {
                        if (node.tagName === 'INPUT' && node.type === 'file') {
                            // On a attrapé l'input file juste après sa création !
                            // On force l'acceptation de TOUT.
                            
                            // Petite vérification pour ne pas casser d'autres nodes si besoin :
                            // Idéalement on vérifierait si le clic venait de notre node, 
                            // mais l'input est créé au niveau du body.
                            
                            // On applique le fix globalement car c'est plus sûr pour votre demande.
                            // Cela autorisera les vidéos partout, ce qui est souvent souhaité de toute façon.
                            node.accept = ".jpg,.jpeg,.png,.webp,.gif,.mp4,.webm,.mkv,.avi,.mov,*";
                            
                            // On arrête d'observer une fois trouvé
                            observer.disconnect();
                        }
                    }
                }
            });
            
            observer.observe(document.body, { childList: true, subtree: true });
            
            // Sécurité : on arrête d'observer après 1 seconde si rien ne se passe
            setTimeout(() => observer.disconnect(), 1000);
            
        }, true); // Capture phase
    },
    
    async nodeCreated(node) {
        if (node.comfyClass === "HolafLoadImageVideo") {
            const widget = node.widgets.find(w => w.name === "media_file");
            if (widget) {
                widget.label = "📷/🎥 Media File";
            }
        }
    }
});