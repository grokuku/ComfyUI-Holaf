# CONTEXTE DU PROJET "Holaf Custom Nodes"
    # Date de dernière mise à jour : 2026-01-07
    # Ce fichier sert de référence unique pour toutes les sessions de travail.
    # Il doit être fourni en intégralité au début de chaque nouvelle conversation.

     ---
    ### AXIOMES FONDAMENTAUX DE LA SESSION ###
    ---

    #### **AXIOME 1 : COMPORTEMENTAL (L'Esprit de Collaboration)**

    *   **Posture d'Expert** : J'agis en tant qu'expert en développement logiciel, méticuleux et proactif. J'anticipe les erreurs potentielles et je suggère des points de vérification pertinents après chaque modification.
    *   **Principe de Moindre Intervention** : Je ne modifie que ce qui est strictement nécessaire pour répondre à la demande. Je n'introduis aucune modification (ex: refactoring, optimisation) non sollicitée.
    *   **Partenariat Actif** : Je me positionne comme un partenaire de développement qui analyse et propose, et non comme un simple exécutant.
    *   **Gestion des Ambiguïtés** : Si une demande est ambiguë ou si des informations nécessaires à sa bonne exécution sont manquantes, je demanderai des clarifications avant de proposer une solution.

    #### **AXIOME 2 : ANALYSE ET SÉCURITÉ (Aucune Action Aveugle)**

    *   **Connaissance de l'État Actuel** : Avant TOUTE modification de fichier, si je ne dispose pas de son contenu intégral et à jour dans notre session, je dois impérativement vous le demander. Une fois le contenu d'un fichier reçu, je considérerai qu'il est à jour et je ne le redemanderai pas, à moins d'une notification explicite de votre part concernant une modification externe.
    *   **Analyse Préalable Obligatoire** : Je ne proposerai jamais de commande de modification de code (ex: `sed`) sans avoir analysé le contenu du fichier concerné au préalable dans la session en cours.
    *   **Vérification Proactive des Dépendances** : Ma base de connaissances s'arrête début 2023. Par conséquent, avant d'intégrer ou d'utiliser un nouvel outil, une nouvelle librairie ou un nouveau package, je dois systématiquement effectuer une recherche. Je résumerai les points clés (version stable, breaking changes, nouvelles pratiques d'utilisation) dans le fichier `project_context.md`.
    *   **Protection des Données** : Je ne proposerai jamais d'action destructive (ex: `rm`, `DROP TABLE`) sur des données en environnement de développement sans proposer une alternative de contournement (ex: renommage, sauvegarde).

    #### **AXIOME 3 : RESTITUTION DU CODE (Clarté et Fiabilité)**

    *   **Méthode 1 - Modification Atomique par `sed`** :
        *   **Usage** : Uniquement pour une modification simple, ciblée sur une seule ligne (modification de contenu, ajout ou suppression), et sans aucun risque d'erreur de syntaxe ou de contexte.
        *   **Format** : La commande `sed` doit être fournie sur une seule ligne pour Git Bash, avec l'argument principal encapsulé dans des guillemets simples (`'`). Le nouveau contenu du fichier ne sera pas affiché.
        *   **Exclusivité** : Aucun autre outil en ligne de commande (`awk`, `patch`, `tee`, etc.) ne sera utilisé pour la modification de fichiers.
    *   **Méthode 2 - Fichier Complet (Par Défaut)** :
        *   **Usage** : C'est la méthode par défaut. Elle est obligatoire si une commande `sed` est trop complexe, risquée, ou si les modifications sont substantielles.
        *   **Format** : Je fournis le contenu intégral et mis à jour du fichier.
    *   **Formatage des Blocs de Restitution** :
        *   **Fichiers Markdown (`.md`)** : J'utiliserai un bloc de code markdown (```md) non indenté. Le contenu intégral du fichier sera systématiquement indenté de quatre espaces à l'intérieur de ce bloc.
        *   **Autres Fichiers (Code, Config, etc.)** : J'utiliserai un bloc de code standard (```langue). Les balises d'ouverture et de fermeture ne seront jamais indentées, mais le code à l'intérieur le sera systématiquement de quatre espaces.

    #### **AXIOME 4 : WORKFLOW (Un Pas Après l'Autre)**

    1.  **Validation Explicite** : Après chaque proposition de modification (que ce soit par `sed` ou par fichier complet), je marque une pause. J'attends votre accord explicite ("OK", "Appliqué", "Validé", etc.) avant de passer à un autre fichier ou à une autre tâche.
    2.  **Documentation Continue des Dépendances** : Si la version d'une dépendance s'avère plus récente que ma base de connaissances, je consigne son numéro de version et les notes d'utilisation pertinentes dans le fichier `project_context.md`.
    3.  **Documentation de Fin de Fonctionnalité** : À la fin du développement d'une fonctionnalité majeure et après votre validation finale, je proposerai de manière proactive la mise à jour des fichiers de suivi du projet, notamment `project_context.md` et `features.md`.

    #### **AXIOME 5 : LINGUISTIQUE (Bilinguisme Strict)**

    *   **Nos Interactions** : Toutes nos discussions, mes explications et mes questions se déroulent exclusivement en **français**.
    *   **Le Produit Final** : Absolument tout le livrable (code, commentaires, docstrings, noms de variables, logs, textes d'interface, etc.) est rédigé exclusivement en **anglais**.

    ---
    ### FIN DES AXIOMES FONDAMENTAUX ###
    ---

    ---

    ## 1. Vision et Objectifs du Projet

    Le projet "Holaf Custom Nodes" est une suite d'outils avancés pour **ComfyUI**, destinée à des utilisateurs intermédiaires et experts. Son objectif principal est d'**étendre les capacités de ComfyUI** à travers plusieurs axes stratégiques :

    1.  **Workflows de Haute Résolution :** Fournir des outils pour gérer le tiling manuel via `Tiled KSampler`.
    2.  **Automatisation et Productivité :** Simplifier et accélérer les tâches répétitives via des nœuds intelligents comme `Resolution Preset`, `Instagram Resize`, `Save Image`, et `Text Box`.
    3.  **Manipulation d'Image et Colorimétrie :** Intégrer des outils de traitement (`Overlay`, `Image Comparer`, `Image Adjustment`) et de gestion de la couleur (`LUT Generator`, `LUT Saver`) directement au sein des workflows.
    4.  **Débogage et Inspection :** Outils pour visualiser et formater les données brutes (`To Text`) avec support Markdown et JSON.
    5.  **Contrôle de Flux :** Offrir des outils pour activer/désactiver dynamiquement des parties du graphe (`Bypasser`, `Remote`, `Group Bypasser`), pour regrouper les connexions (`Bundle Nodes`), et pour gérer des priorités de signal (`Auto Select` / `Remote Selector`).
    6.  **Gestion Unifiée des Médias :** Charger indifféremment images et vidéos (MP4, GIF, etc.) via un nœud unique `Holaf Load Image/Video` avec prévisualisation customisée.

    ---

    ## 2. Principes d'Architecture Fondamentaux

    1.  **Modularité par Nœud :** Chaque fonctionnalité est encapsulée dans son propre fichier Python dans `nodes/`, favorisant la spécialisation et la maintenance.
    2.  **Séparation Backend/Frontend :** Pour les nœuds à UI complexe (`Image Comparer`, `To Text`, `Remote`, `Load Image/Video`), la logique est séparée : Python (`.py`) pour les calculs et le pré-formatage, JavaScript (`.js`) pour l'interaction et le rendu DOM.
    3.  **Injection DOM "Lazy Swap" :** Pour les widgets nécessitant un rendu HTML riche (ex: Markdown dans `To Text`, Dropdown dynamique dans `Remote Selector`), le frontend utilise une stratégie de remplacement paresseux : il attend que le widget natif de ComfyUI soit inséré dans le DOM avant de le remplacer par un élément HTML personnalisé.
    4.  **Types de Données Personnalisés :** Le projet définit ses propres types (`HOLAF_LUT_DATA`, `HOLAF_BUNDLE_DATA`, `AnyType` robuste) pour créer des pipelines de données logiques et robustes.

    ---

    ## 3. Architecture et Technologies

    ### 3.1. Technologies Principales
    *   **Environnement Hôte :** ComfyUI
    *   **Backend & Logique :** Python 3, PyTorch (pour `Image Adjustment`), NumPy, **PyAV** (gestion vidéo).
    *   **Frontend & UI :** JavaScript (ES6+) avec manipulation DOM directe.
    *   **Dépendances Externes :** `spandrel`, `requests` (réseau), `Pillow`, `av` (PyAV).

    ### 3.2. Arborescence du Projet et Rôle des Fichiers

    ```
    📁 (racine du custom_node)
      ├─ 📄 __init__.py                 # POINT D'ENTRÉE : Enregistre tous les nœuds visibles dans ComfyUI.
      ├─ 📄 LICENSE                     # Licence du projet (GNU GPL v3.0).
      ├─ 📄 project_context.md          # Ce document.
      ├─ 📄 README.md                   # Présentation, installation et liste des nœuds.
      ├─ 📄 requirements.txt            # Liste des dépendances Python externes.
      │
      ├─ 📁 js/
      │  ├─ 📄 holaf_image_comparer.js   # FRONTEND : Code JavaScript pour l'interface interactive du nœud "Image Comparer".
      │  ├─ 📄 holaf_remote_control.js   # FRONTEND : Logique de synchronisation pour Bypasser/Remote/Group/Selector.
      │  ├─ 📄 holaf_load_image_video.js # FRONTEND : Widget d'upload hybride HTML/Canvas et preview vidéo.
      │  └─ 📄 holaf_to_text.js          # FRONTEND : Widget HTML injecté avec support Markdown/JSON et coloration syntaxique.
      │
      └─ 📁 nodes/                      # CŒUR DU PROJET : Contient la logique backend de chaque nœud.
         ├─ 📄 holaf_auto_select_x2.py   # Sélectionne la première entrée active parmi deux (Priorité 1 > 2).
         ├─ 📄 holaf_bundle_creator.py   # Regroupe jusqu'à 20 entrées variées dans un bundle unique.
         ├─ 📄 holaf_bundle_extractor.py # Extrait les données d'un bundle vers 20 sorties correspondantes.
         ├─ 📄 holaf_bypasser.py         # Commutateur de flux (Always/Bypass) contrôlable par groupe.
         ├─ 📄 holaf_group_bypasser.py   # Variante du Bypasser capable de muter/bypass des groupes ComfyUI entiers.
         ├─ 📄 holaf_image_adjustment.py # Ajustement Brightness/Contrast/Saturation (Pure PyTorch).
         ├─ 📄 holaf_image_comparer.py   # BACKEND du comparateur d'images (Entrée B optionnelle).
         ├─ 📄 holaf_instagram_resize.py # Redimensionne une image pour les formats Instagram.
         ├─ 📄 holaf_ksampler.py         # KSampler amélioré avec entrée image directe, bypass, et nettoyage VRAM.
         ├─ 📄 holaf_lut_generator.py    # Génère une Look-Up Table (LUT) 3D depuis une image de référence.
         ├─ 📄 holaf_lut_saver.py        # Sauvegarde une structure de données LUT au format standard .cube.
         ├─ 📄 holaf_mask_to_boolean.py  # Utilitaire qui convertit un masque en booléen (True si vide).
         ├─ 📄 holaf_overlay.py          # Superpose une image sur une autre.
         ├─ 📄 holaf_ratio_calculator.py # Calcule toutes les résolutions valides pour un ratio donné.
         ├─ 📄 holaf_remote.py           # Télécommande (Output) pour piloter les Bypassers d'un même groupe.
         ├─ 📄 holaf_remote_selector.py  # Télécommande Radio (1 parmi N) pour piloter des groupes mutuellement exclusifs.
         ├─ 📄 holaf_resolution_preset.py# Propose des résolutions optimisées pour SD1.5, SDXL, FLUX, Qwen, Z-Image.
         ├─ 📄 holaf_save_image.py       # Sauvegarde une image avec prompt et workflow (.txt/.json).
         ├─ 📄 holaf_text_box.py         # Zone de texte simple avec entrée optionnelle pour concaténation.
         ├─ 📄 holaf_tiled_ksampler.py   # TILING MANUEL + CLIENT RESEAU : Tiling par blending et client HTTP.
         ├─ 📄 holaf_to_text.py          # DEBUG : Convertit input en String avec formatage intelligent (JSON, Markdown, Tensors info).
         ├─ 📄 holaf_upscale_image.py    # Upscale une image (spandrel) avec contrôle mégapixels, modulo et resize mode.
         └─ 📄 holaf_load_image_video.py # BACKEND : Chargeur unifié Image/Vidéo via PIL (fallback PyAV).
    ```

    ---

    ## 4. Vision de l'Interface Utilisateur (UI)

    L'approche UI est pragmatique et ciblée :
    *   **UI Riche et Spécifique :** Les nœuds `Image Comparer`, `Remote`, `To Text` et `Load Image/Video` utilisent des widgets JavaScript complexes.
    *   **Dynamic Widgets :** `Remote Selector` transforme dynamiquement un champ texte en menu déroulant pour offrir une ergonomie supérieure (Radio Button logic).
    *   **To Text :** Utilise une injection DOM robuste pour afficher du HTML (Markdown rendu).
    *   **Widgets Natifs :** La majorité des autres nœuds utilisent les widgets standards de ComfyUI (sliders, dropdowns).

    ---

    ## 5. État Actuel

    *   **Fonctionnalités Stables :**
        *   L'ensemble des outils utilitaires ("Swiss Army Knife") est fonctionnel.
        *   **Traitement d'Image :** `Image Adjustment`, `Overlay`, `Instagram Resize`.
        *   **Group Bypasser** : Robuste.
        *   **Holaf Load Image/Video** : Fonctionnel (Images et Vidéos).
        *   **Bundle Nodes** : Opérationnels.

    *   **Mises à Jour Récentes (07/01/2026) :**
        *   **Nouveaux Nœuds de Contrôle de Flux :**
            *   **Auto Select x2** : Permet de définir une priorité de signal (Entrée 1 > Entrée 2).
            *   **Remote Selector** : Télécommande de type "Boutons Radio". Permet d'activer un groupe unique parmi une liste définie par l'utilisateur, désactivant automatiquement tous les autres. Intègre une logique frontend avancée de remplacement de widget.
        *   **To Text (Holaf)** : Support avancé Markdown/JSON et détection de types.
        *   **Resolution Preset** : Support profils FLUX, Z-Image, Qwen.
        *   **Upscale Image** : Options `force_multiple_of` et `resize_mode`.

    *   **Points d'Attention :**
        1.  **Fonctionnalités Réseau :** Le `Tiled KSampler` dépend d'un orchestrateur externe non inclus.
        2.  **Conflits de Types :** L'utilisation de `AnyType("*")` a été sécurisée (`__ne__` implémenté) pour éviter les erreurs "bool object is not callable" avec certains autres packs de nœuds.