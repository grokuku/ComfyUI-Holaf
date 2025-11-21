# CONTEXTE DU PROJET "Holaf Custom Nodes"
# Date de dernière mise à jour : 2025-08-05
# Ce fichier sert de référence unique pour toutes les sessions de travail.
# Il doit être fourni en intégralité au début de chaque nouvelle conversation.

## 0. Règles de Collaboration et de Session

### 0.1. Instructions pour l'Assistant IA

1.  **Demande Systématique du Contenu des Fichiers à Modifier :** Pour toute tâche qui m'impose de modifier un fichier, si le contenu intégral et actuel de ce fichier ne m'a pas été explicitement fourni au préalable durant notre session, je dois impérativement te le demander avant toute autre action. Je ne proposerai jamais de modification (ni de commande `sed`, ni de contenu de fichier complet) tant que tu ne m'auras pas fourni le contenu du fichier que j'ai demandé.

2.  **Format des modifications de fichiers :**
    *   Lorsqu'une modification est apportée à un fichier, je fournirai une commande `sed` pour Git Bash, **en une seule ligne**, permettant d'appliquer ce patch. (L'argument de la commande sed sera encapsulé dans des guillemets simples ').
    *   **Condition :** Je ne fournirai cette commande `sed` que si elle est basique et ne risque pas de générer une erreur.
    *   Dans ce cas (commande `sed` sans risque), je ne montrerai pas les blocs de code modifiés, je donnerai uniquement la commande `sed`.
    *   **Restriction d'outil :** Je n'utiliserai que `sed` pour ces commandes de patch. Je n'utiliserai jamais d'autres outils (comme `patch`, `awk`, `tee`, etc.).
    *   **Alternative :** Si la commande `sed` requise (en respectant la contrainte d'une seule ligne) risquait de ne pas fonctionner correctement, ou si une commande `sed` en une seule ligne n'est pas réalisable, je ne fournirai pas de commande. À la place, je te donnerai le contenu intégral du fichier modifié.

3.  **Flux de travail séquentiel :** Après avoir proposé une modification (commande `sed` ou fichier complet), j'attendrai explicitement ton accord avant de proposer des modifications pour un fichier suivant ou de continuer sur une autre tâche.

4.  **Principe de moindre intervention :** Je ne modifierai pas de sections de code qui fonctionnent correctement si cela n'est pas explicitement demandé ou absolument nécessaire pour la tâche en cours. Je ne ferai aucune optimisation de code si ce n'est pas explicitement demandé.

5.  **Anticipation des erreurs et suggestion de vérification :** Après avoir proposé une modification, je suggérerai brièvement les points clés que tu devrais vérifier ou les tests simples que tu pourrais effectuer pour t'assurer du bon fonctionnement.

6.  **Format de Présentation des Fichiers :** Pour garantir que le contenu des fichiers puisse être copié facilement et sans erreur de formatage, je présenterai systématiquement tout contenu de fichier intégral en l'indentant de quatre espaces ligne par ligne.

### 0.2. Instruction Initiale (pour l'utilisateur)

Pour démarrer une session, utilise le prompt suivant :
"Voici un projet (les fichiers et l'arborescence te seront fournis). Analyse-le attentivement. Une fois ton analyse terminée, signale-moi que tu es prêt à commencer à travailler sur les modifications en respectant les règles ci-dessus."

---

## 1. Vision et Objectifs du Projet

Le projet "Holaf Custom Nodes" est une suite d'outils avancés pour **ComfyUI**, destinée à des utilisateurs intermédiaires et experts. Son objectif principal est d'**étendre les capacités de ComfyUI** à travers plusieurs axes stratégiques :

1.  **Workflows de Très Haute Résolution :** Fournir des outils robustes pour générer et manipuler des images à des résolutions dépassant les limites de la VRAM, en utilisant des techniques de tiling allant du blending manuel aux algorithmes de diffusion avancés (`Mixture of Diffusers`).
2.  **Automatisation et Productivité :** Simplifier et accélérer les tâches répétitives via des nœuds intelligents comme `Resolution Preset`, `Instagram Resize`, et `Save Image` (sauvegarde enrichie).
3.  **Analyse de Performance :** Offrir une suite de benchmarking complète (`Loader`, `Runner`, `Plotter`) pour mesurer et visualiser objectivement les performances des modèles et du matériel.
4.  **Manipulation d'Image et Colorimétrie :** Intégrer des outils de traitement (`Overlay`, `Image Comparer`) et de gestion de la couleur (`LUT Generator`, `LUT Saver`) directement au sein des workflows.
5.  **Calcul Distribué (Expérimental) :** Proposer une architecture d'**Orchestrateur** pour déporter les tâches de sampling sur des machines distantes ("workers"), transformant ComfyUI en un poste de contrôle.

---

## 2. Principes d'Architecture Fondamentaux

1.  **Modularité par Nœud :** Chaque fonctionnalité est encapsulée dans son propre fichier Python dans `nodes/`, favorisant la spécialisation et la maintenance.
2.  **Séparation Backend/Frontend :** Pour les nœuds à UI complexe (`Image Comparer`), la logique est séparée : Python (`.py`) pour les calculs, JavaScript (`.js`) pour l'interaction via un widget personnalisé.
3.  **Dégradation Grâcieuse :** Les nœuds avec des dépendances externes (`pandas`, `matplotlib`, `psutil`) vérifient leur disponibilité et se désactivent ou fonctionnent en mode limité si elles sont absentes, informant l'utilisateur dans la console.
4.  **Types de Données Personnalisés :** Le projet définit ses propres types (`HOLAF_LUT_DATA`, `HOLAF_MODEL_INFO_LIST`, `ORCHESTRATOR_CONFIG`) pour créer des pipelines de données logiques et robustes entre ses nœuds.
5.  **Interopérabilité :** Les nœuds utilisent et retournent les types natifs de ComfyUI (`IMAGE`, `MODEL`, `LATENT`, etc.), garantissant une intégration transparente dans les workflows existants.
6.  **Architecture Client-Serveur (Orchestrateur) :** Le système de calcul distribué repose sur une communication HTTP. Les données complexes (tenseurs) sont sérialisées (`pickle` + `base64`) pour le transport.

---

## 3. Architecture et Technologies

### 3.1. Technologies Principales
*   **Environnement Hôte :** ComfyUI
*   **Backend & Logique :** Python 3, PyTorch, NumPy
*   **Frontend & UI :** JavaScript (ES6+)
*   **Dépendances Externes :** `spandrel`, `pandas`, `matplotlib`, `psutil`, `requests`

### 3.2. Arborescence du Projet et Rôle des Fichiers

```
📁 (racine du custom_node)
  ├─ 📄 __init__.py                 # POINT D'ENTRÉE : Enregistre tous les nœuds visibles dans ComfyUI en mappant les noms de classe aux fichiers.
  ├─ 📄 LICENSE                     # Licence du projet (GNU GPL v3.0).
  ├─ 📄 project_context.md          # Ce document.
  ├─ 📄 README.md                   # Présentation, installation et liste des nœuds.
  ├─ 📄 requirements.txt            # Liste des dépendances Python externes.
  │
  ├─ 📁 js/
  │  └─ 📄 holaf_image_comparer.js   # FRONTEND : Code JavaScript pour l'interface interactive du nœud "Image Comparer".
  │
  └─ 📁 nodes/                      # CŒUR DU PROJET : Contient la logique backend de chaque nœud.
     ├─ 📄 HolafBenchmarkLoader.py   # Suite Benchmark [1/3] : Charge les modèles SD/FLUX et les prépare pour le Runner.
     ├─ 📄 HolafBenchmarkPlotter.py  # Suite Benchmark [3/3] : Prend le CSV du Runner et génère des graphiques de performance.
     ├─ 📄 HolafBenchmarkRunner.py   # Suite Benchmark [2/3] : Exécute les tests de vitesse et génère un rapport en format CSV.
     ├─ 📄 HolafInternalSampler.py   # Orchestrateur [WORKER] : Nœud destiné aux machines distantes, reçoit des données sérialisées et exécute un sampling.
     ├─ 📄 holaf_image_comparer.py   # BACKEND du comparateur d'images.
     ├─ 📄 holaf_instagram_resize.py # Redimensionne une image pour les formats Instagram par ajout de bandes (padding).
     ├─ 📄 holaf_ksampler.py         # KSampler amélioré avec entrée image directe, bypass, et nettoyage VRAM.
     ├─ 📄 holaf_lut_generator.py    # Génère une Look-Up Table (LUT) 3D depuis une image de référence.
     ├─ 📄 holaf_lut_saver.py        # Sauvegarde une structure de données LUT au format standard .cube.
     ├─ 📄 holaf_mask_to_boolean.py  # Utilitaire qui convertit un masque en booléen (True si vide).
     ├─ 📄 holaf_orchestrator_config.py # Orchestrateur [CLIENT] : Configure l'adresse du serveur et les workers actifs.
     ├─ 📄 holaf_overlay.py          # Superpose une image sur une autre.
     ├─ 📄 holaf_ratio_calculator.py # Calcule toutes les résolutions valides pour un ratio donné.
     ├─ 📄 holaf_resolution_preset.py# Propose des résolutions optimisées (largeur/hauteur) pour SD1.5, SDXL, FLUX.
     ├─ 📄 holaf_save_image.py       # Sauvegarde une image et, en option, le prompt et le workflow dans des fichiers .txt/.json.
     ├─ 📄 holaf_slice_calculator.py # Calcule le nombre de "tranches" (X et Y) nécessaires pour couvrir une image.
     ├─ 📄 holaf_tile_calculator.py  # Calcule les dimensions exactes d'une tuile pour un pavage parfait.
     ├─ 📄 holaf_tiled_diffusion_ksampler.py # TILING AVANCÉ : Implémente des algorithmes (`Mixture of Diffusers`) via patching du modèle. Maintenant actif.
     ├─ 📄 holaf_tiled_ksampler.py   # TILING MANUEL + RESEAU : Implémente un tiling par blending manuel et contient la logique client pour l'orchestrateur.
     └─ 📄 holaf_upscale_image.py    # Upscale une image à un nombre de mégapixels cible.
```

---

## 4. Vision de l'Interface Utilisateur (UI)

L'approche UI est pragmatique et ciblée :
*   **UI Riche et Spécifique :** Le `HolafImageComparer` utilise un widget JavaScript complexe et sur-mesure pour une interaction avancée (modes "Slide" et "Click").
*   **UI Générée :** Le `HolafBenchmarkPlotter` n'a pas d'UI interactive, mais *génère* un élément visuel (une image de graphique) comme restitution des résultats.
*   **Widgets Natifs :** La majorité des nœuds utilisent les widgets standards de ComfyUI (sliders, dropdowns), garantissant une intégration et une expérience utilisateur cohérentes.

---

## 5. État Actuel et Feuille de Route

*   **État Actuel :**
    Le projet est une collection de nœuds fonctionnels et expérimentaux. L'intégration récente du `Tiled Diffusion KSampler` rend le set d'outils de haute résolution plus complet. Le statut global reste expérimental et "AS IS".

*   **Points d'Attention et Problèmes Connus :**
    1.  **Coexistence des Tiled Samplers :** Bien que les deux Tiled Samplers soient maintenant fonctionnels et clairement nommés (`Tiled KSampler` et `Tiled Diffusion KSampler`), leur existence en tant que deux nœuds distincts peut prêter à confusion. De plus, la logique réseau de l'orchestrateur est uniquement présente dans le `Tiled KSampler` (méthode manuelle).
    2.  **Dépendances Externes :** Le bon fonctionnement de la suite de benchmark et de l'upscaler dépend de l'installation correcte des paquets listés dans `requirements.txt`.
    3.  **Orchestrateur Incomplet :** Le projet fournit le client (`Tiled KSampler` en mode réseau) et le worker (`InternalSampler`), mais pas le code du serveur orchestrateur lui-même.

*   **Feuille de Route Potentielle :**
    1.  **Rationalisation des Samplers :** La prochaine étape logique serait de fusionner les deux Tiled Samplers en un seul nœud. Ce nœud unifié pourrait avoir un sélecteur de "méthode" : `Manual Blend`, `Mixture of Diffusers`, `Network (Orchestrator)`. Cela simplifierait grandement l'expérience utilisateur.
    2.  **Support de FLUX dans le Benchmark :** Finaliser l'implémentation du `Benchmark Runner` pour qu'il puisse tester correctement les modèles de type FLUX.
    3.  **Documentation :** Enrichir le `README.md` avec des exemples de workflows, notamment pour illustrer la différence et l'utilisation des deux Tiled Samplers.
    4.  **Développement de l'Orchestrateur :** Fournir un exemple de serveur d'orchestration pour rendre la fonctionnalité de calcul distribué utilisable.