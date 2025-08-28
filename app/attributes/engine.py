# app/attributes/engine.py
import json
import os
from typing import Optional
from app.schemas.attributes import AttributeQuestion

ATTR_FILE = os.path.join(os.path.dirname(__file__), "attributes.json")

def _load_attributes() -> dict:
    if not os.path.exists(ATTR_FILE):
        raise FileNotFoundError(f"attributes.json introuvable à: {ATTR_FILE}")
    try:
        with open(ATTR_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("attributes.json doit contenir un objet racine (dict).")
            return data
    except json.JSONDecodeError as e:
        raise ValueError(f"attributes.json invalide (JSONDecodeError): {e}") from e

# Chargement au démarrage
ATTRIBUTES = _load_attributes()

def next_question(session: dict) -> Optional[AttributeQuestion]:
    """
    Retourne la prochaine question à poser selon attributes.json
    et les réponses déjà présentes en session.
    """
    selected_subcat = session.get("subcategory") or session.get("sub_category") or session.get("subcat")
    if not selected_subcat:
        # Pour Phase 2a on cible 'voitures'; on aide gentiment si absent
        selected_subcat = "voitures"

    questions = ATTRIBUTES.get(selected_subcat)
    if not questions:
        raise KeyError(f"Aucune configuration d'attributs pour la sous-catégorie: {selected_subcat}")

    answered = session.get("attributes", {})

    for q in questions:
        field = q.get("field")
        if field and field not in answered:
            return AttributeQuestion(
                field=field,
                question=q.get("question", f"Veuillez renseigner {field}"),
                options=q.get("options")
            )

    # toutes les questions déjà répondues
    return None

