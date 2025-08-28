import json, re, os
from fastapi import HTTPException
from app.core.config import CATALOG_PATH, CATALOG_FILTER_TYPE, CATALOG_FILTER_CATEGORY
import unicodedata


#  Utilitaire: transforme un label en ID "slug"
#  "Véhicules & Transport" -> "vehicules-transport"
_slug_re = re.compile(r"[^a-z0-9]+")
def slugify(label: str) -> str:
    s = label.strip().lower()
    s = _slug_re.sub("-", s).strip("-")
    return s

#  Charge le JSON brut depuis le disque
def load_raw():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

#  Construit une structure standardisée pour /catalog
def build_catalog():
    raw = load_raw()
    categories = []
    for block in raw:
        #  Filtres .env (facultatifs) pour n'exposer qu'une partie du catalogue
        if CATALOG_FILTER_TYPE and block.get("type") != CATALOG_FILTER_TYPE:
            continue
        if CATALOG_FILTER_CATEGORY and block.get("nameCategory") != CATALOG_FILTER_CATEGORY:
            continue

        #  Catégorie
        cat_label = block.get("nameCategory")
        if not cat_label:
            continue
        cat_id = slugify(cat_label)

        #  Sous-catégories
        subs = []
        for sub in block.get("subCategory", []):
            sub_label = sub.get("name")
            if not sub_label:
                continue
            sub_id = slugify(sub_label)
            subs.append({"id": sub_id, "label": sub_label})

        categories.append({"id": cat_id, "label": cat_label, "subcategories": subs})

    return {
        "version": "1.0.0",
        "type_filter": CATALOG_FILTER_TYPE,
        "category_filter": CATALOG_FILTER_CATEGORY,
        "categories": categories
    }

#  Vérifie que la sous-catégorie demandée appartient bien à la catégorie
def validate_selection(category_id: str, subcategory_id: str) -> bool:
    cat = build_catalog()
    for c in cat["categories"]:
        if c["id"] == category_id:
            return any(s["id"] == subcategory_id for s in c["subcategories"])
    return False
def load_raw():
    # Log/erreur explicite si le fichier n'existe pas
    if not os.path.exists(CATALOG_PATH):
        raise HTTPException(
            status_code=500,
            detail=f"CATALOG_PATH introuvable: {CATALOG_PATH}. Vérifie .env et la présence de data/categories.json."
        )
    try:
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"categories.json invalide (JSONDecodeError): {e}"
        )
        
 

_slug_re = re.compile(r"[^a-z0-9]+")

def slugify(label: str) -> str:
    """
    Transforme un libellé (avec accents/espaces) en ID slug ASCII propre.
    Exemple: 'Véhicules & Transport' -> 'vehicules-transport'
             'Vélos & Trottinettes' -> 'velos-trottinettes'
    """
    if not label:
        return ""
    # 1) Supprimer les accents (NFKD) -> ASCII
    s = unicodedata.normalize("NFKD", label)
    s = s.encode("ascii", "ignore").decode("ascii")
    # 2) minuscules
    s = s.lower().strip()
    # 3) remplace tout ce qui n'est pas a-z0-9 par '-'
    s = _slug_re.sub("-", s).strip("-")
    # 4) compacter les tirets multiples
    s = re.sub(r"-{2,}", "-", s)
    return s
