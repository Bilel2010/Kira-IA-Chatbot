# app/core/config.py
import os
from pathlib import Path

# (Optionnel mais pratique) charge automatiquement .env s'il existe
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv()
except Exception:
    pass

APP_NAME = "Kira Seller Chatbot"
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
SESSION_SECRET = os.getenv("SESSION_SECRET", "CHANGE_ME")

# ➜ BASE_DIR = racine du projet (kira-chatbot-svc-v2)
BASE_DIR = Path(__file__).resolve().parents[2]

# Si CATALOG_PATH n'est pas défini dans l'env, on pointe vers <BASE_DIR>/data/categories.json
CATALOG_PATH = os.getenv("CATALOG_PATH", str(BASE_DIR / "data" / "categories.json"))

# (Optionnels pour filtrer ce que tu exposes)
CATALOG_FILTER_TYPE = os.getenv("CATALOG_FILTER_TYPE")
CATALOG_FILTER_CATEGORY = os.getenv("CATALOG_FILTER_CATEGORY")

# Prépa Phase 3 (non utilisé ici)
LLM_ENABLED = os.getenv("LLM_ENABLED", "false").lower() == "true"
MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "models" / "mistral-7b-instruct.Q4_K_M.gguf"))
MODEL_CTX = int(os.getenv("MODEL_CTX", "8192"))
MODEL_N_THREADS = int(os.getenv("MODEL_N_THREADS", "4"))


