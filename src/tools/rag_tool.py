"""RAG (Retrieval Augmented Generation) integration helper."""

from __future__ import annotations

from typing import Any, List


class VectorDBConnectionError(RuntimeError):
    """Raised when the vector database client cannot be instantiated."""


class VectorDBClient:
    """Wrapper mínimo para operações de similaridade."""

    def __init__(self, backend: Any) -> None:
        self.backend = backend
        self._collection = None
        self._collection_name = "btf-default"

    def similarity_search(self, query: str, k: int) -> List[Any]:
        if hasattr(self.backend, "similarity_search"):
            return self.backend.similarity_search(query, k)
        if hasattr(self.backend, "query"):
            response = self.backend.query(query_texts=[query], n_results=k)
            return response.get("documents", [[]])[0]
        if hasattr(self.backend, "get_or_create_collection"):
            if self._collection is None:
                self._collection = self.backend.get_or_create_collection(self._collection_name)
            response = self._collection.query(query_texts=[query], n_results=k)
            return response.get("documents", [[]])[0]
        raise NotImplementedError("Vector DB backend must implement similarity_search().")


def connect_to_vectordb(vector_db_url: str) -> VectorDBClient:
    """Retorna um cliente básico para o banco vetorial configurado."""

    try:
        import chromadb  # type: ignore
    except ImportError as exc:  # pragma: no cover - explicit guidance
        raise VectorDBConnectionError(
            "chromadb must be installed to connect to the vector database"
        ) from exc

    from urllib.parse import urlparse

    parsed = urlparse(vector_db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8000

    if hasattr(chromadb, "HttpClient"):
        backend = chromadb.HttpClient(host=host, port=port)
    else:  # Fallback for older chromadb versions
        backend = chromadb.Client()

    return VectorDBClient(backend)


class RAGTool:
    def __init__(self, vector_db_url: str) -> None:
        self.db = connect_to_vectordb(vector_db_url)

    def retrieve(self, query: str, k: int = 5):
        """Recupera contexto relevante do banco vetorial."""

        return self.db.similarity_search(query, k)
