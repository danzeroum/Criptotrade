"""Persistent memory management with optional ChromaDB."""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Try to import ChromaDB, but don't fail if unavailable
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class AgentMemorySystem:
    """Manage agent memories with optional vector store."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or Path(".buildtovalue/ledger")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.episodic_path = self.storage_dir / "agent_memories.jsonl"

        # Initialize vector store only if available
        self.collection = None
        if CHROMADB_AVAILABLE:
            self._init_vector_store()

    def _init_vector_store(self):
        """Initialize ChromaDB vector store."""
        try:
            client = chromadb.Client()
            self.collection = client.get_or_create_collection("agent_memories")
        except Exception:
            self.collection = None

    def remember_decision(self, agent: str, decision: Dict[str, Any]) -> None:
        """Store decision in episodic memory."""
        entry = {
            "agent": agent,
            "decision": decision,
            "timestamp": decision.get("timestamp"),
        }

        # Always write to file (fallback)
        with open(self.episodic_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        # Optionally store in vector DB
        if self.collection:
            try:
                self.collection.add(
                    documents=[json.dumps(decision)],
                    metadatas=[{"agent": agent}],
                    ids=[f"{agent}_{decision.get('timestamp')}"]
                )
            except Exception:
                # Vector-store write is best-effort; the JSONL file above is the
                # durable record. Log at debug instead of swallowing silently.
                logger.debug("Vector-store add failed; using file-only fallback", exc_info=True)

    def recall(self, query: str, n_results: int = 5) -> List[Dict]:
        """Recall similar past decisions."""
        # If no vector store, return empty
        if not self.collection:
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            return results
        except Exception:
            return []

    # Backwards compatible API expected by orchestrator/tests
    def recall_similar(self, query: str, k: int = 5) -> List[Dict]:
        """Compatibility wrapper around :meth:`recall`."""
        return self.recall(query, n_results=k)
