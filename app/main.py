# app/main.py
from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

# ─────────────────────────────────────────────────────────
# CHARGEMENT .env (robuste)
# ─────────────────────────────────────────────────────────
def _strip_inline_comment(val: str) -> str:
    """
    Supprime un commentaire inline non quoté.
    Règle simple: si la valeur n'est pas entre quotes '...' ou "..."
    alors on coupe au premier '#' précédé d'un espace/tab.
    """
    s = val
    if not s:
        return s
    # déjà sans quotes -> regarder ' #' ou '\t#'
    idx_space_hash = s.find(" #")
    idx_tab_hash = s.find("\t#")
    idx_hash_start = s.find("#")
    cut_positions = [p for p in [idx_space_hash, idx_tab_hash] if p != -1]
    # si la valeur commence par un # (ligne tout commentaire)
    if idx_hash_start == 0:
        return ""
    if cut_positions:
        cut = min(cut_positions)
        return s[:cut].rstrip()
    return s

def _unquote(val: str) -> str:
    if len(val) >= 2 and ((val[0] == val[-1] == "'") or (val[0] == val[-1] == '"')):
        return val[1:-1]
    return val

def _force_load_env() -> None:
    """
    Lit .env (UTF-8 avec BOM possible) et injecte TOUT dans os.environ.
    Gère:
      - BOM sur la première clé
      - commentaires en fin de ligne (#) si valeur non quotée
      - espaces et accents dans les valeurs
      - guillemets englobants
    """
    env_path = Path(__file__).resolve().parents[1] / ".env"
    print("⚙️  ENV: target .env ->", env_path, "| exists:", env_path.exists())
    if not env_path.exists():
        return

    applied = 0
    try:
        # utf-8-sig enlève automatiquement le BOM en tête de fichier
        with env_path.open("r", encoding="utf-8-sig") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip().lstrip("\ufeff")  # anti-BOM sur la clé
                v = v.strip()

                # Si valeur quotée -> on enlève uniquement les quotes
                if (len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"')):
                    v = _unquote(v)
                else:
                    # sinon, on retire commentaire inline (#) tolérant
                    v = _strip_inline_comment(v)

                # override inconditionnel
                os.environ[k] = v
                applied += 1

        print(f"⚙️  ENV: applied {applied} key(s) from .env (forced override)")
    except Exception as e:
        print("❌ ENV: error reading .env:", e)

# Charger .env AVANT toute importation qui lit les env
_force_load_env()

# ─────────────────────────────────────────────────────────
# Imports qui lisent l'env APRÈS chargement .env
# ─────────────────────────────────────────────────────────
from app.core.config import APP_VERSION, SESSION_SECRET
from app.routers.cat import router as category_router
from app.routers.attb import router as attb_router
from app.routers.publish_flow import router as flow_router

# ─────────────────────────────────────────────────────────
# FastAPI
# ─────────────────────────────────────────────────────────
app = FastAPI(title="Kira Seller Chatbot", version=APP_VERSION)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")

# Logs startup non sensibles
@app.on_event("startup")
def _startup_logs():
    print("⚙️  STARTUP: APP_VERSION =", APP_VERSION)
    print("⚙️  STARTUP: LLM_PROVIDER =", os.getenv("LLM_PROVIDER", "(vide)"))
    print("⚙️  STARTUP: LLAMA_CPP_MODEL_PATH =", os.getenv("LLAMA_CPP_MODEL_PATH", "(vide)"))

@app.get("/healthz")
def healthz():
    return {
        "ok": True,
        "service": "kira-seller-bot",
        "version": APP_VERSION,
        "llm_provider": os.getenv("LLM_PROVIDER"),
        "llama_model_path": os.getenv("LLAMA_CPP_MODEL_PATH"),
    }

# Routers
app.include_router(category_router)    # catalog + publish/select-category
app.include_router(attb_router)        # publish/attributes
app.include_router(flow_router)        # publish/flow






