"""Extra coverage for rag_tool.py — RAGTool and connect_to_vectordb."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


def _inject_chromadb(monkeypatch) -> MagicMock:
    """Inject a mock chromadb module and return it."""
    mock_chromadb = MagicMock()
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_chromadb.HttpClient.return_value = mock_client
    mock_chromadb.Client.return_value = mock_client  # fallback
    mock_client.get_or_create_collection.return_value = mock_collection
    mock_client.similarity_search.return_value = ["result"]
    monkeypatch.setitem(sys.modules, "chromadb", mock_chromadb)
    return mock_chromadb


def test_connect_to_vectordb_uses_http_client(monkeypatch):
    """Lines 44-51: HttpClient path when chromadb.HttpClient exists."""
    mock_chromadb = _inject_chromadb(monkeypatch)
    # Ensure HttpClient attr is present on mock (default MagicMock has it)
    from src.tools import rag_tool
    client = rag_tool.connect_to_vectordb("http://localhost:8000")
    assert client is not None
    mock_chromadb.HttpClient.assert_called_once_with(host="localhost", port=8000)


def test_connect_to_vectordb_fallback_client(monkeypatch):
    """Lines 52-53: older chromadb without HttpClient → uses chromadb.Client()."""
    mock_chromadb = _inject_chromadb(monkeypatch)
    # Remove HttpClient to trigger fallback
    del mock_chromadb.HttpClient
    from src.tools import rag_tool
    client = rag_tool.connect_to_vectordb("http://localhost:8001")
    assert client is not None
    mock_chromadb.Client.assert_called_once()


def test_rag_tool_init_and_retrieve(monkeypatch):
    """Lines 59-65: RAGTool.__init__ and retrieve delegate to VectorDBClient."""
    mock_chromadb = _inject_chromadb(monkeypatch)
    mock_backend = mock_chromadb.HttpClient.return_value
    mock_backend.similarity_search.return_value = ["ctx1", "ctx2"]

    from src.tools import rag_tool
    tool = rag_tool.RAGTool("http://localhost:8000")
    results = tool.retrieve("BTC trend", k=2)
    assert results == ["ctx1", "ctx2"]


def test_rag_tool_retrieve_default_k(monkeypatch):
    """retrieve() defaults to k=5."""
    mock_chromadb = _inject_chromadb(monkeypatch)
    mock_backend = mock_chromadb.HttpClient.return_value
    mock_backend.similarity_search.return_value = ["a", "b", "c", "d", "e"]

    from src.tools import rag_tool
    tool = rag_tool.RAGTool("http://localhost:8000")
    results = tool.retrieve("market analysis")
    mock_backend.similarity_search.assert_called_with("market analysis", 5)
    assert len(results) == 5
