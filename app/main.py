from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import APP_VERSION, SESSION_SECRET

# Phase 1
from app.routers.cat import router as category_router
# Phase 2a
from app.routers.attb import router as attb_router
# Phase 2b
from app.routers.publish_flow import router as flow_router  # ← NEW

# Crée l’application
app = FastAPI(title="Kira Seller Chatbot", version=APP_VERSION)

# Active la gestion de sessions (cookies côté client)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax")

# Endpoint de santé
@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "kira-seller-bot", "version": APP_VERSION}

# Monter les routers
app.include_router(category_router)   # contient catalog + publish/select-category
app.include_router(attb_router)       # contient publish/attributes
app.include_router(flow_router)       # contient publish/flow/start + publish/flow/reply



