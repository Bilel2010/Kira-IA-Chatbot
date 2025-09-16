# app/services/llm_service.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

class LLMClient:
    """
    Client IA (LOCAL UNIQUEMENT) via llama-cpp-python.
    - Provider forcé: 'llama_cpp_local'
    - Requiert LLAMA_CPP_MODEL_PATH dans l'environnement
    """

    def __init__(self) -> None:
        self.provider: str = "llama_cpp_local"
        self._client: Any = None

        # Paramètres génération (runtime)
        self._max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "256"))
        self._temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.6"))
        self._top_p: float = float(os.getenv("LLM_TOP_P", "0.9"))

        # Contexte / threads (runtime)
        self._n_ctx: int = int(os.getenv("LLAMA_CPP_CTX", "4096"))
        self._n_threads: int = int(os.getenv("MODEL_N_THREADS", "4"))

        print("🤖 LLM init (local):",
              "model_path=", os.getenv("LLAMA_CPP_MODEL_PATH"),
              "n_ctx=", self._n_ctx,
              "threads=", self._n_threads)

    # ------------- API publique -------------
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> str:
        temperature = self._temperature if temperature is None else temperature
        max_tokens = self._max_tokens if max_tokens is None else max_tokens
        top_p = self._top_p if top_p is None else top_p
        return self._chat_llama_cpp(messages, temperature, max_tokens, top_p)

    # ------------- LLAMA.CPP (local) -------------
    def _ensure_llama_cpp(self) -> None:
        if self._client is not None:
            return

        model_path_raw = (os.getenv("LLAMA_CPP_MODEL_PATH") or "").strip()
        if not model_path_raw:
            raise RuntimeError("LLAMA_CPP_MODEL_PATH manquant pour l'inférence locale.")

        # Résolution en chemin absolu (si relatif à la racine du repo)
        p = Path(model_path_raw)
        if not p.is_absolute():
            # repo root = parents[2] (app/services/... -> repo/)
            repo_root = Path(__file__).resolve().parents[2]
            p = (repo_root / p).resolve()

        print(f"🧭 Resolved model path: {p} | exists: {p.exists()}")
        if not p.exists():
            raise RuntimeError(f"Fichier modèle introuvable: {p}")

        try:
            from llama_cpp import Llama  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "Le package 'llama-cpp-python' n'est pas installé. Installe-le: pip install llama-cpp-python"
            ) from e

        try:
            print(f"🔄 Chargement du modèle local: {p}")
            self._client = Llama(
                model_path=str(p),
                n_ctx=self._n_ctx,
                n_threads=self._n_threads,
            )
            print("✅ Modèle local chargé")
        except Exception as e:
            print(f"❌ Erreur lors du chargement du modèle ({p}): {e}")
            raise

    def _chat_llama_cpp(
        self, messages: List[Dict[str, str]], temperature: float, max_tokens: int, top_p: float
    ) -> str:
        self._ensure_llama_cpp()
        try:
            out = self._client.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )
            return (out["choices"][0]["message"]["content"] or "").strip()
        except Exception as e:
            print(f"❌ Erreur llama_cpp: {e}")
            return ""

# Singleton
_client: Optional[LLMClient] = None

def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
        print("🤖 LLM client initialisé (provider local)")
    return _client


