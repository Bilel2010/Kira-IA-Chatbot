from fastapi import APIRouter, Request, HTTPException
from app.schemas.category import CatalogOut, CategorySelectionIn, CategorySelectionOut
from app.services.catalog_service import build_catalog, validate_selection
from app.services.session_store import get_post_session, save_post_session

#  Pref. d'API (v1) et tags pour Swagger
router = APIRouter(prefix="/api/v1", tags=["catalog", "publish"])

# ─────────────────────────────────────────────────────────
# GET /api/v1/catalog
# → Sert au front pour afficher la liste Catégorie / Sous-catégorie avec IDs
# ─────────────────────────────────────────────────────────
@router.get("/catalog", response_model=CatalogOut)
def get_catalog():
    return build_catalog()

# ─────────────────────────────────────────────────────────
# POST /api/v1/publish/select-category
# Body: { category_id, subcategory_id, locale?, attributes_mode? }
# → Valide les IDs + stocke en session → renvoie le prochain état du flux
# ─────────────────────────────────────────────────────────
@router.post("/publish/select-category", response_model=CategorySelectionOut)
def select_category(payload: CategorySelectionIn, request: Request):
    # 1) Validation : le couple (categorie, sous-categorie) existe-t-il ?
    if not validate_selection(payload.category_id, payload.subcategory_id):
        raise HTTPException(status_code=400, detail="Catégorie/sous-catégorie invalides")

    # 2) Mise à jour de la session "post"
    post = get_post_session(request)
    post.update({
        "category_id": payload.category_id,
        "subcategory_id": payload.subcategory_id,
        "locale": payload.locale or "fr",
        "attributes_mode": payload.attributes_mode or "chatbot",
        "flow_state": "await_attributes",  # prochaine étape = collecte attributs
        "collected_attributes": {},        # vide pour Phase 1
    })
    save_post_session(request, post)

    # 3) Réponse claire pour le front
    return CategorySelectionOut(
        ok=True,
        message="Catégorie enregistrée.",
        flow_state="await_attributes",
        category_id=payload.category_id,
        subcategory_id=payload.subcategory_id,
        session_id="auto",  # info indicative (cookie côté client)
        next_action="/api/v1/publish/collect-attributes"
    )

