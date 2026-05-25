"""RAG package with lazy exports."""

from __future__ import annotations

from typing import Any

__all__ = ["Embedder", "HybridRetriever", "Reranker"]


def __getattr__(name: str) -> Any:
    if name == "Embedder":
        from app.rag.embedder import Embedder
        return Embedder
    if name == "HybridRetriever":
        from app.rag.retriever import HybridRetriever
        return HybridRetriever
    if name == "Reranker":
        from app.rag.reranker import Reranker
        return Reranker
    raise AttributeError(name)
