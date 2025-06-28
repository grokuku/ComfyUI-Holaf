# Fichier: holaf_orchestrator_config.py
# Node pour configurer la connexion à Holaf-Orchestrator

class HolafOrchestratorConfig:
    """
    Node pour configurer la connexion à Holaf-Orchestrator et 
    sélectionner les workers à utiliser pour une tâche.
    """
    @classmethod
    def INPUT_TYPES(s):
        inputs = {
            "required": {
                "address": ("STRING", {"default": "http://127.0.0.1:8000"}),
            }
        }
        # Créer statiquement 5 emplacements pour les workers
        for i in range(1, 6):
            inputs["required"][f"worker_{i}_name"] = ("STRING", {"default": ""})
            inputs["required"][f"worker_{i}_toggle"] = (["OFF", "ON"],)
            
        return inputs

    RETURN_TYPES = ("ORCHESTRATOR_CONFIG",)
    FUNCTION = "configure"
    CATEGORY = "Holaf"

    def configure(self, address, **kwargs):
        active_workers = []
        for i in range(1, 6):
            name = kwargs.get(f"worker_{i}_name", "").strip()
            toggle = kwargs.get(f"worker_{i}_toggle", "OFF")
            
            if name and toggle == "ON":
                active_workers.append(name)

        config = {
            "address": address,
            "active_workers": active_workers
        }
        
        # Le retour est une liste contenant un dictionnaire
        return (config,)