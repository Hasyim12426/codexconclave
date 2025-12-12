"""Chronicle — unified memory system for Arbiters and Conclaves.

The :class:`Chronicle` provides a simple, pluggable interface for
storing and retrieving memories.  It delegates persistence to a
:class:`~codexconclave.chronicle.store.BaseChronicleStore` backend.
"""

from __future__ import annotations

import logging
from typing import Any

from codexconclave.chronicle.store import (
    BaseChronicleStore,
    ChronicleEntry,
    InMemoryChronicleStore,
)

logger = logging.getLogger(__name__)


class Chronicle:
    """Unified memory system for Arbiters and Conclaves.

    Provides ``remember`` / ``recall`` / ``summarize_context``
    operations backed by any :class:`BaseChronicleStore`.

    Example::

        memory = Chronicle(arbiter_role="Researcher")
        memory.remember("AI was coined in 1956 by John McCarthy.")
        entries = memory.recall("AI history")
        print(entries[0].content)
    """

    def __init__(
        self,
        store: BaseChronicleStore | None = None,
        arbiter_role: str | None = None,
        max_entries: int = 1000,
    ) -> None:
        """Initialise a Chronicle.

        Args:
            store: Storage backend.  Defaults to
                :class:`~codexconclave.chronicle.store.InMemoryChronicleStore`.
            arbiter_role: Optional role label stamped on all entries as
                metadata, useful for filtering in shared memory stores.
            max_entries: Soft limit on entries.  When exceeded, the
                oldest entries are pruned during :meth:`remember`.
        """
        self._store = store or InMemoryChronicleStore()
        self._arbiter_role = arbiter_role
        self._max_entries = max_entries
        self._logger = logging.getLogger(__name__)

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def remember(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ChronicleEntry:
        """Store a new memory entry.

        When the store exceeds :attr:`max_entries`, the oldest entries
        are pruned to stay within the limit.

        Args:
            content: The text content to remember.
            metadata: Optional metadata attached to the entry.

        Returns:
            ChronicleEntry: The created memory entry.
        """
        effective_metadata = dict(metadata or {})
        if self._arbiter_role:
            effective_metadata["arbiter_role"] = self._arbiter_role

        entry = ChronicleEntry.create(
            content=content,
            metadata=effective_metadata,
        )
        self._store.save(entry)

        self._logger.debug("Chronicle.remember: stored entry %s", entry.id)
        return entry

    def recall(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> list[ChronicleEntry]:
        """Retrieve relevant memories for a query.

        Args:
            query: The search query string.
            limit: Maximum number of entries to return.
            min_score: Minimum relevance score threshold (0.0–1.0).

        Returns:
            list[ChronicleEntry]: Matching entries sorted by
                relevance descending.
        """
        results = self._store.search(
            query=query,
            limit=limit,
            score_threshold=min_score,
        )
        self._logger.debug(
            "Chronicle.recall: query='%s' returned %d entries",
            query[:60],
            len(results),
        )
        return results

    def summarize_context(self, query: str) -> str:
        """Return a formatted string of relevant memories for ``query``.

        Suitable for injecting into an LLM prompt as additional
        context.

        Args:
            query: The query to retrieve memories for.

        Returns:
            str: Formatted memory context, or empty string if none
                found.
        """
        entries = self.recall(query)
        if not entries:
            return ""

        parts: list[str] = []
        for i, entry in enumerate(entries, start=1):
            parts.append(f"{i}. {entry.content}")

        return "Relevant memories:\n" + "\n".join(parts)

    def clear(self) -> None:
        """Remove all stored memories."""
        self._store.clear()
        self._logger.debug("Chronicle cleared.")

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Return the total number of stored memories.

        Returns:
            int: Memory count.
        """
        return self._store.count()

    def __repr__(self) -> str:
        """Return a developer-friendly string representation.

        Returns:
            str: Repr string.
        """
        role_part = (
            f" role='{self._arbiter_role}'" if self._arbiter_role else ""
        )
        return f"Chronicle({len(self)} entries{role_part})"
