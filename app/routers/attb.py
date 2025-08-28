# app/routers/attb.py
from fastapi import APIRouter, Request
from app.schemas.attributes import AttributeAnswer, AttributeQuestion
from app.attributes.engine import next_question
from app.services.session_store import get_post_session, save_post_session

router = APIRouter(prefix="/api/v1/publish", tags=["publish-attributes"])

# ─────────────────────────────────────────────
# Phase 2a : collecte attributs simple
# ─────────────────────────────────────────────
@router.post("/attributes", response_model=AttributeQuestion | None)
def answer_attribute(answer: AttributeAnswer, request: Request):
    """
    Reçoit une réponse d'attribut (ex: {"field": "marque", "value": "Peugeot"}),
    la sauvegarde en session, puis renvoie la prochaine question.
    """
    session = get_post_session(request)
    session.setdefault("subcategory", "voitures")
    session["attributes"] = session.get("attributes", {})
    session["attributes"][answer.field] = answer.value
    save_post_session(request, session)
    return next_question(session)


