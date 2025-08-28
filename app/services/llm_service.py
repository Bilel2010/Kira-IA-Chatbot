# app/services/llm_service.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING

# ─────────────────────────────────────────────────────────
# Providers disponibles :
# - "mock"            : pas d'appel externe, utile dev/tests
# - "mistral"         : API cloud via SDK "mistralai" (optionnel)
# - "llama_cpp_local" : modèle local GGUF via "llama-cpp-python" (optionnel)
# ─────────────────────────────────────────────────────────

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").strip().lower()

# Cloud (Mistral)
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

# Local (llama.cpp)
LLAMA_CPP_MODEL_PATH = os.getenv("LLAMA_CPP_MODEL_PATH", "")  # ex: ./models/mistral-7b-instruct.Q4_K_M.gguf
LLAMA_CPP_CTX = int(os.getenv("LLAMA_CPP_CTX", "4096"))

# Génération (communs)
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "256"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.6"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "0.9"))

# Pour éviter les erreurs Pylance lorsque les libs optionnelles ne sont pas installées.
if TYPE_CHECKING:
    # Ces imports ne s’exécutent pas à runtime, uniquement pour l’analyse statique
    try:
        from mistralai import Mistral as _MistralClient  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover
        _MistralClient = Any  # type: ignore[assignment]
    try:
        from llama_cpp import Llama as _LlamaClient  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover
        _LlamaClient = Any  # type: ignore[assignment]
else:  # pragma: no cover
    _MistralClient = Any
    _LlamaClient = Any


class LLMClient:
    """Client IA unifié (mock | mistral | llama_cpp_local)."""

    def __init__(self) -> None:
        self.provider = LLM_PROVIDER
        self._client: Any = None  # client sous-jacent (Mistral ou Llama)

    # ------------- API publique -------------
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> str:
        """
        Chat simple au format OpenAI-like :
        messages = [{"role": "system"|"user"|"assistant", "content": "..."}]
        Retourne un texte (str).
        """
        temperature = LLM_TEMPERATURE if temperature is None else temperature
        max_tokens = LLM_MAX_TOKENS if max_tokens is None else max_tokens
        top_p = LLM_TOP_P if top_p is None else top_p

        if self.provider == "mock":
            return self._chat_mock(messages)

        if self.provider == "mistral":
            return self._chat_mistral(messages, temperature, max_tokens, top_p)

        if self.provider == "llama_cpp_local":
            return self._chat_llama_cpp(messages, temperature, max_tokens, top_p)

        # fallback ultra-sûr
        return self._chat_mock(messages)

    # ------------- Implémentations -------------
    def _chat_mock(self, messages: List[Dict[str, str]]) -> str:
        """Réponse déterministe, pratique pour dev/local sans coûts."""
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        txt = (last_user or "OK").strip()
        if len(txt) > 200:
            txt = txt[:200] + "..."
        return txt

    # ---- Mistral cloud (optionnel) ----
    def _ensure_mistral(self) -> None:
        if self._client is not None:
            return
        if not MISTRAL_API_KEY:
            raise RuntimeError("MISTRAL_API_KEY manquant pour provider 'mistral'.")
        # Import tardif pour ne JAMAIS casser si le package n'est pas installé.
        try:
            from mistralai import Mistral  # type: ignore[import-not-found]
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Le package 'mistralai' n'est pas installé. Faites: pip install mistralai"
            ) from e
        self._client = Mistral(api_key=MISTRAL_API_KEY)

    def _chat_mistral(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        top_p: float,
    ) -> str:
        self._ensure_mistral()
        # Selon versions du SDK, l'API peut varier.
        # Ici on utilise la forme courante:
        try:
            resp = self._client.chat.complete(
                model=MISTRAL_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            return ""

    # ---- llama.cpp local (optionnel) ----
    def _ensure_llama_cpp(self) -> None:
        if self._client is not None:
            return
        if not LLAMA_CPP_MODEL_PATH:
            raise RuntimeError("LLAMA_CPP_MODEL_PATH manquant pour provider 'llama_cpp_local'.")
        try:
            from llama_cpp import Llama  # type: ignore[import-not-found]
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "Le package 'llama-cpp-python' n'est pas installé. "
                "Faites: pip install llama-cpp-python"
            ) from e

        # Instanciation du modèle (chargement en mémoire)
        self._client = Llama(
            model_path=LLAMA_CPP_MODEL_PATH,
            n_ctx=LLAMA_CPP_CTX,
            # tu peux ajouter n_threads, n_gpu_layers, etc. selon ta machine
        )

    def _chat_llama_cpp(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        top_p: float,
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
        except Exception:
            return ""


# Singleton simple pour éviter de recharger le modèle
_client: Optional[LLMClient] = None

def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
