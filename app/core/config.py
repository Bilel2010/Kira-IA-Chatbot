# app/core/config.py
import os
from pathlib import Path

APP_NAME = "Kira Seller Chatbot"
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
SESSION_SECRET = os.getenv("SESSION_SECRET", "CHANGE_ME")

# Racine du projet (kira-chatbot-svc-v2)
BASE_DIR = Path(__file__).resolve().parents[2]

# Chemin du catalogue si besoin (fallback local)
CATALOG_PATH = os.getenv("CATALOG_PATH", str(BASE_DIR / "data" / "categories.json"))

# Filtres optionnels
CATALOG_FILTER_TYPE = os.getenv("CATALOG_FILTER_TYPE")
CATALOG_FILTER_CATEGORY = os.getenv("CATALOG_FILTER_CATEGORY")

# Note: la config LLM est lue directement dans app/services/llm_service.py




