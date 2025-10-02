"""Persistent memory management utilities for agents."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore
except Exception:  # pragma: no cover - fallback
    chromadb = None
    Settings = None  # type: ignore


class _FallbackCollection:
    def __init__(self) -> None:
        self._items: List[Dict[str, Any]] = []

    def add(self, *, documents: List[str], metadatas: List[Dict[str, Any]], ids: List[str]) -> None:
        for doc, meta, id_ in zip(documents, metadatas, ids):
            self._items.append({"id": id_, "document": doc, "metadata": meta})

    def query(self, query_texts: List[str], n_results: int = 5) -> Dict[str, Any]:
        return {"ids": [], "metadatas": [], "documents": [], "query": query_texts, "n_results": n_results}


class AgentMemorySystem:
    """Manage short, long, and episodic memories for agents."""

    def __init__(self, storage_dir: Optional[Path] = None) -> None:
        self.short_term: Dict[str, Any] = {}
        self.storage_dir = storage_dir or Path(".BuildToValue/ledger")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.episodic_path = self.storage_dir / "agent_memories.jsonl"

        self.collection = self._initialise_vector_store()

    def _initialise_vector_store(self):
        if chromadb is None or Settings is None:
            return _FallbackCollection()

        try:
            client = chromadb.Client(
                Settings(
                    chroma_server_host="localhost",
                    chroma_server_http_port=8000,
                    chroma_client_auth_provider="no_auth",  # matches open-source container defaults
                )
            )
            try:
                return client.create_collection("agent_memories")
            except Exception:
                return client.get_collection("agent_memories")
        except Exception:
            return _FallbackCollection()

    def remember_decision(self, agent: str, decision: Dict[str, Any]) -> None:
        """Persist an important decision to disk and vector storage."""

        memory = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "decision": decision,
            "confidence": float(decision.get("confidence", 0.0)),
        }
        with self.episodic_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(memory, ensure_ascii=False) + "\n")

        self.collection.add(
            documents=[json.dumps(decision, ensure_ascii=False)],
            metadatas=[{"agent": agent, "timestamp": memory["timestamp"]}],
            ids=[f"{agent}_{memory['timestamp']}"],
        )

    def recall_similar(self, query: str, k: int = 5) -> Dict[str, Any]:
        """Retrieve similar memories using the vector database (or fallback)."""

        return self.collection.query(query_texts=[query], n_results=k)
