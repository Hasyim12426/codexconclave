"""Chronicle storage backends for CodexConclave memory.

Provides an abstract :class:`BaseChronicleStore` and a built-in
:class:`InMemoryChronicleStore` that uses substring matching.  For
production use with vector embeddings, swap in a LanceDB or ChromaDB
backed store.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChronicleEntry:
    """A single stored memory entry.

    Attributes:
        id: Unique identifier for this entry.
        content: The textual content of the memory.
        embedding: Optional vector embedding of the content.
        score: Relevance score assigned during retrieval.
        created_at: UTC timestamp of creation.
        metadata: Arbitrary key-value metadata.
    """

    id: str
    content: str
    embedding: list[float] | None
    score: float
    created_at: datetime
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChronicleEntry:
        """Create a new :class:`ChronicleEntry` with auto-generated id.

        Args:
            content: The text content to store.
            metadata: Optional dictionary of metadata.

        Returns:
            ChronicleEntry: A freshly created entry.
        """
        return cls(
            id=str(uuid.uuid4()),
            content=content,
            embedding=None,
            score=0.0,
            created_at=datetime.utcnow(),
            metadata=metadata or {},
        )


class BaseChronicleStore(ABC):
    """Abstract storage backend for Chronicle memory.

    Implement this to integrate a vector database, SQL store, or any
    other persistence mechanism.
    """

    @abstractmethod
    def save(self, entry: ChronicleEntry) -> None:
        """Persist a memory entry.

        Args:
            entry: The entry to store.
        """

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.0,
    ) -> list[ChronicleEntry]:
        """Retrieve entries relevant to ``query``.

        Args:
            query: The search query string.
            limit: Maximum number of results to return.
            score_threshold: Minimum relevance score (0.0–1.0).

        Returns:
            list[ChronicleEntry]: Matching entries ordered by
                relevance descending.
        """

    @abstractmethod
    def clear(self) -> None:
        """Remove all stored entries."""

    @abstractmethod
    def count(self) -> int:
        """Return the total number of stored entries.

        Returns:
            int: Entry count.
        """


class InMemoryChronicleStore(BaseChronicleStore):
    """Simple in-memory store using substring matching.

    Suitable for development, testing, and low-volume use cases.
    For production, use a vector-backed store for semantic search.
    """

    def __init__(self) -> None:
        """Initialise an empty in-memory store."""
        self._entries: list[ChronicleEntry] = []

    def save(self, entry: ChronicleEntry) -> None:
        """Append the entry to the in-memory list.

        Args:
            entry: The memory entry to persist.
        """
        self._entries.append(entry)
        logger.debug(
            "Chronicle: saved entry %s (%d chars)",
            entry.id,
            len(entry.content),
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        score_threshold: float = 0.0,
    ) -> list[ChronicleEntry]:
        """Return entries whose content contains the query substring.

        A simple relevance score is computed based on term frequency
        so that more relevant entries sort higher.

        Args:
            query: The search query string.
            limit: Maximum number of results.
            score_threshold: Minimum score (0.0 = no threshold).

        Returns:
            list[ChronicleEntry]: Matching entries sorted by score.
        """
        query_lower = query.lower()
        # Filter short stop words to improve signal-to-noise ratio
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "what",
            "which",
            "who",
            "whom",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "of",
            "in",
            "on",
            "at",
            "to",
            "for",
            "with",
            "by",
            "from",
            "or",
        }
        query_terms = [
            t
            for t in query_lower.split()
            if len(t) > 2 and t not in stop_words
        ] or query_lower.split()

        scored: list[tuple[float, ChronicleEntry]] = []

        for entry in self._entries:
            content_lower = entry.content.lower()

            # Count how many query terms appear in the content
            hits = sum(1 for t in query_terms if t in content_lower)
            if hits == 0:
                continue

            score = hits / max(len(query_terms), 1)

            if score >= score_threshold:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:limit]]

    def clear(self) -> None:
        """Remove all entries from the store."""
        self._entries.clear()
        logger.debug("Chronicle: store cleared")

    def count(self) -> int:
        """Return the number of stored entries.

        Returns:
            int: Entry count.
        """
        return len(self._entries)
