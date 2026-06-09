"""Embeddings provider abstraction.

Two implementations:
- `openai`: hits the Platform embeddings endpoint, requires LLM_API_KEY.
- `local`:  loads a sentence-transformers multilingual model in-process. No API
            key needed — runs entirely offline after the first model download.
            Default: `intfloat/multilingual-e5-small` (384 dims, 117 MB), strong
            on Arabic and English.
"""
from __future__ import annotations

import threading
from typing import Protocol

from openai import OpenAI

from app.core.config import settings


class EmbeddingsProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbeddings:
    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.llm_api_key)
        self._model = settings.embeddings_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # OpenAI accepts up to ~2048 inputs per call; chunk to be safe.
        out: list[list[float]] = []
        BATCH = 64
        for i in range(0, len(texts), BATCH):
            batch = texts[i : i + BATCH]
            resp = self._client.embeddings.create(model=self._model, input=batch)
            out.extend([d.embedding for d in resp.data])
        return out


class LocalEmbeddings:
    """sentence-transformers model. Loaded lazily and cached process-wide."""

    _model = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._model_name = settings.embeddings_model
        # e5 family expects "passage: " / "query: " prefixes; we only index
        # passages here. Distinguishing query at retrieve-time is a future tweak.
        self._is_e5 = "e5" in self._model_name.lower()

    @classmethod
    def _load(cls, name: str):
        if cls._model is None:
            with cls._lock:
                if cls._model is None:
                    from sentence_transformers import SentenceTransformer
                    cls._model = SentenceTransformer(name)
        return cls._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load(self._model_name)
        if self._is_e5:
            inputs = [f"passage: {t}" for t in texts]
        else:
            inputs = texts
        # encode returns a numpy array; convert to nested list for psycopg/pgvector.
        vecs = model.encode(inputs, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
        return [v.tolist() for v in vecs]


def get_embeddings_provider() -> EmbeddingsProvider:
    if settings.embeddings_provider == "local":
        return LocalEmbeddings()
    return OpenAIEmbeddings()
