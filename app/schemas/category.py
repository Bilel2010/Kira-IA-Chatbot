from pydantic import BaseModel, Field
from typing import Optional, Literal, List

# ▶ Forme d'une sous-catégorie renvoyée au front dans /catalog
class CatalogSubcategory(BaseModel):
    id: str         # ex: "voitures"
    label: str      # ex: "Voitures"

# ▶ Forme d'une catégorie renvoyée au front dans /catalog
class CatalogCategory(BaseModel):
    id: str                      # ex: "vehicules-transport"
    label: str                   # ex: "Véhicules & Transport"
    subcategories: List[CatalogSubcategory]

# ▶ Payload de réponse du GET /catalog
class CatalogOut(BaseModel):
    version: str                 # ex: "1.0.0"
    type_filter: Optional[str] = None
    category_filter: Optional[str] = None
    categories: List[CatalogCategory]

# ▶ Payload reçu du front lors du POST /publish/select-category
class CategorySelectionIn(BaseModel):
    category_id: str = Field(..., min_length=1)     # ex: "vehicules-transport"
    subcategory_id: str = Field(..., min_length=1)  # ex: "voitures"
    locale: Optional[str] = "fr"                    # info utile pour la suite
    attributes_mode: Optional[Literal["manual","chatbot","hybrid"]] = "chatbot"

# ▶ Payload renvoyé au front après enregistrement en session
class CategorySelectionOut(BaseModel):
    ok: bool
    message: str                                     # message humain
    flow_state: Literal["await_attributes"]          # prochain état
    category_id: str
    subcategory_id: str
    session_id: str                                  # (indicatif) géré par cookie
    next_action: str                                 # endpoint à appeler ensuite

