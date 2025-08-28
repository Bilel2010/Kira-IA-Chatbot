# app/services/session_store.py
from __future__ import annotations

from typing import Any, Callable, Dict
from copy import deepcopy
from fastapi import Request

POST_KEY = "post"  # clé unique pour stocker l’annonce en cours


def get_post_session(request: Request) -> Dict[str, Any]:
    """
    Récupère l'état courant de la publication (annonce en cours).
    ⚠️ Important:
      - On retourne un *nouveau dict* (copie superficielle) pour éviter
        les mutations en place sur request.session[POST_KEY] qui ne
        marqueraient pas automatiquement la session comme modifiée.
      - Après toute modification, appeler `save_post_session(...)`.
    """
    stored = request.session.get(POST_KEY) or {}
    # copie superficielle suffisante ici (les sous-dicts seront réécrits via save_post_session)
    return dict(stored)


def save_post_session(request: Request, data: Dict[str, Any]) -> None:
    """
    Sauvegarde/écrase l'état de la publication courante.
    Note: on réassigne la clé POST_KEY pour que Starlette marque la
    session comme modifiée (sinon mutations profondes non détectées).
    """
    request.session[POST_KEY] = data


def clear_post_session(request: Request) -> None:
    """
    Réinitialise complètement la session de publication.
    """
    request.session[POST_KEY] = {}


# ─────────────────────────────────────────────────────────
# Helpers facultatifs (pratiques pour gérer la sous-clé "flow")
# ─────────────────────────────────────────────────────────

def get_flow_session(request: Request) -> Dict[str, Any]:
    """
    Récupère le sous-objet flow dans la session de publication.
    Retourne un dict (copie) avec clés par défaut si absent.
    Pensez à réécrire via `set_flow_session` après modification.
    """
    post = request.session.get(POST_KEY) or {}
    flow = post.get("flow") or {}
    if not isinstance(flow, dict):
        flow = {}
    # valeurs par défaut
    flow.setdefault("id", "publish.voitures.v1")
    flow.setdefault("vars", {})
    flow.setdefault("counters", {})
    flow.setdefault("current", None)
    return dict(flow)


def set_flow_session(request: Request, flow: Dict[str, Any]) -> None:
    """
    Écrit / remplace le sous-objet flow dans la session de publication.
    Utilise save_post_session pour forcer la réécriture et marquer la session modifiée.
    """
    post = get_post_session(request)
    post["flow"] = flow
    save_post_session(request, post)


def reset_flow_session(request: Request, *,
                       flow_id: str = "publish.voitures.v1",
                       entry: str = "q_locale") -> None:
    """
    Réinitialise seulement la partie 'flow' de la session de publication.
    Utile si tu veux un reset “soft” (sans effacer le reste de l’annonce).
    """
    post = get_post_session(request)
    post["flow"] = {
        "id": flow_id,
        "vars": {},
        "counters": {},
        "current": entry,
    }
    save_post_session(request, post)


