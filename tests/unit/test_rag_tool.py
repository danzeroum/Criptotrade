"""Tests for VectorDBClient backends in rag_tool.py."""
from __future__ import annotations

import pytest

from src.tools.rag_tool import VectorDBClient


class _DirectSimilarityBackend:
    """Backend with similarity_search method (first priority)."""
    def similarity_search(self, query: str, k: int):
        return [f"result:{query}:{k}"]


class _QueryBackend:
    """Backend with query method but no similarity_search."""
    def query(self, query_texts, n_results):
        return {"documents": [[f"doc:{query_texts[0]}"]]}


class _CollectionBackend:
    """Backend with get_or_create_collection (ChromaDB-like)."""
    def get_or_create_collection(self, name: str):
        return self

    def query(self, query_texts, n_results):
        return {"documents": [[f"col_doc:{query_texts[0]}"]]}


class _NoMethodBackend:
    """Backend with none of the expected methods."""
    pass


def test_similarity_search_direct_backend():
    """Backend with similarity_search → delegate directly."""
    client = VectorDBClient(_DirectSimilarityBackend())
    results = client.similarity_search("test query", 3)
    assert results == ["result:test query:3"]


def test_similarity_search_query_backend():
    """Backend with query method → uses documents[0]."""
    client = VectorDBClient(_QueryBackend())
    results = client.similarity_search("market", 5)
    assert results == ["doc:market"]


def test_similarity_search_collection_backend():
    """Backend with get_or_create_collection → creates collection then queries."""
    client = VectorDBClient(_CollectionBackend())
    results = client.similarity_search("signal", 2)
    assert results == ["col_doc:signal"]


def test_similarity_search_collection_reuses_cached_collection():
    """Second call reuses the cached _collection."""
    client = VectorDBClient(_CollectionBackend())
    client.similarity_search("first", 1)
    first_collection = client._collection
    client.similarity_search("second", 1)
    assert client._collection is first_collection


def test_similarity_search_no_method_raises():
    """Backend with no methods → NotImplementedError."""
    client = VectorDBClient(_NoMethodBackend())
    with pytest.raises(NotImplementedError, match="similarity_search"):
        client.similarity_search("query", 3)


def test_query_backend_missing_documents_returns_empty():
    """query backend returns no 'documents' key → empty list."""
    class _EmptyResponse:
        def query(self, query_texts, n_results):
            return {}

    client = VectorDBClient(_EmptyResponse())
    result = client.similarity_search("q", 1)
    assert result == []
