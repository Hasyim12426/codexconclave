"""Unit tests for the Chronicle memory system."""

from __future__ import annotations

from codexconclave.chronicle.memory import Chronicle
from codexconclave.chronicle.store import (
    ChronicleEntry,
    InMemoryChronicleStore,
)

# ---------------------------------------------------------------------------
# ChronicleEntry tests
# ---------------------------------------------------------------------------


class TestChronicleEntry:
    """Tests for ChronicleEntry creation and fields."""

    def test_create_sets_content(self) -> None:
        """create() should store the provided content."""
        entry = ChronicleEntry.create(content="test memory")
        assert entry.content == "test memory"

    def test_create_generates_id(self) -> None:
        """create() should generate a non-empty unique id."""
        e1 = ChronicleEntry.create("a")
        e2 = ChronicleEntry.create("b")
        assert e1.id
        assert e2.id
        assert e1.id != e2.id

    def test_create_sets_timestamp(self) -> None:
        """create() should set a non-None created_at timestamp."""
        entry = ChronicleEntry.create("x")
        assert entry.created_at is not None

    def test_create_default_metadata_empty(self) -> None:
        """create() with no metadata arg should default to empty dict."""
        entry = ChronicleEntry.create("x")
        assert entry.metadata == {}

    def test_create_with_metadata(self) -> None:
        """create() should store provided metadata."""
        entry = ChronicleEntry.create("x", metadata={"source": "test"})
        assert entry.metadata["source"] == "test"

    def test_default_embedding_none(self) -> None:
        """create() should set embedding to None by default."""
        entry = ChronicleEntry.create("x")
        assert entry.embedding is None

    def test_default_score_zero(self) -> None:
        """create() should set score to 0.0 by default."""
        entry = ChronicleEntry.create("x")
        assert entry.score == 0.0


# ---------------------------------------------------------------------------
# InMemoryChronicleStore tests
# ---------------------------------------------------------------------------


class TestInMemoryChronicleStore:
    """Tests for the in-memory store backend."""

    def test_save_increments_count(self) -> None:
        """save() should increment the count."""
        store = InMemoryChronicleStore()
        assert store.count() == 0
        store.save(ChronicleEntry.create("first"))
        assert store.count() == 1

    def test_save_multiple(self) -> None:
        """Multiple saves should accumulate."""
        store = InMemoryChronicleStore()
        for i in range(5):
            store.save(ChronicleEntry.create(f"entry {i}"))
        assert store.count() == 5

    def test_search_finds_matching_content(self) -> None:
        """search() should return entries containing the query."""
        store = InMemoryChronicleStore()
        store.save(ChronicleEntry.create("AI was invented in 1956"))
        store.save(ChronicleEntry.create("Cats are popular pets"))

        results = store.search("AI")
        assert len(results) == 1
        assert "AI" in results[0].content

    def test_search_case_insensitive(self) -> None:
        """search() should be case-insensitive."""
        store = InMemoryChronicleStore()
        store.save(ChronicleEntry.create("Machine Learning basics"))

        results = store.search("machine learning")
        assert len(results) == 1

    def test_search_no_match_returns_empty(self) -> None:
        """search() with no match should return empty list."""
        store = InMemoryChronicleStore()
        store.save(ChronicleEntry.create("Python is great"))

        results = store.search("quantum physics")
        assert results == []

    def test_search_respects_limit(self) -> None:
        """search() should respect the limit parameter."""
        store = InMemoryChronicleStore()
        for i in range(10):
            store.save(ChronicleEntry.create(f"AI topic {i}"))

        results = store.search("AI", limit=3)
        assert len(results) <= 3

    def test_clear_removes_all(self) -> None:
        """clear() should remove all entries."""
        store = InMemoryChronicleStore()
        store.save(ChronicleEntry.create("entry"))
        store.clear()
        assert store.count() == 0

    def test_search_after_clear_returns_empty(self) -> None:
        """After clear(), search should return empty."""
        store = InMemoryChronicleStore()
        store.save(ChronicleEntry.create("AI"))
        store.clear()
        assert store.search("AI") == []


# ---------------------------------------------------------------------------
# Chronicle tests
# ---------------------------------------------------------------------------


class TestChronicle:
    """Tests for the Chronicle memory facade."""

    def test_remember_returns_entry(self) -> None:
        """remember() should return a ChronicleEntry."""
        memory = Chronicle()
        entry = memory.remember("I learned about Python.")
        assert isinstance(entry, ChronicleEntry)

    def test_remember_increments_len(self) -> None:
        """len(memory) should grow after remember()."""
        memory = Chronicle()
        memory.remember("fact 1")
        memory.remember("fact 2")
        assert len(memory) == 2

    def test_recall_returns_relevant_entries(self) -> None:
        """recall() should return entries matching the query."""
        memory = Chronicle()
        memory.remember("The Eiffel Tower is in Paris, France.")
        memory.remember("Python was created by Guido van Rossum.")

        results = memory.recall("Eiffel Tower")
        assert len(results) >= 1
        assert any("Eiffel" in r.content for r in results)

    def test_recall_respects_limit(self) -> None:
        """recall() should respect the limit parameter."""
        memory = Chronicle()
        for i in range(10):
            memory.remember(f"AI fact {i}")

        results = memory.recall("AI", limit=3)
        assert len(results) <= 3

    def test_summarize_context_returns_string(self) -> None:
        """summarize_context() should return a formatted string."""
        memory = Chronicle()
        memory.remember("Neural networks are inspired by biology.")
        summary = memory.summarize_context("neural networks")
        assert isinstance(summary, str)
        assert "neural" in summary.lower()

    def test_summarize_context_empty_returns_empty_string(
        self,
    ) -> None:
        """summarize_context() with no matches returns empty string."""
        memory = Chronicle()
        result = memory.summarize_context("obscure topic xyz")
        assert result == ""

    def test_clear_resets_length(self) -> None:
        """clear() should reset length to zero."""
        memory = Chronicle()
        memory.remember("test")
        memory.clear()
        assert len(memory) == 0

    def test_arbiter_role_stamped_on_entries(self) -> None:
        """When arbiter_role is set, it should appear in entry metadata."""
        memory = Chronicle(arbiter_role="Researcher")
        entry = memory.remember("some fact")
        assert entry.metadata.get("arbiter_role") == "Researcher"

    def test_repr_includes_entry_count(self) -> None:
        """repr should include the current entry count."""
        memory = Chronicle()
        memory.remember("x")
        r = repr(memory)
        assert "1" in r

    def test_custom_store_is_used(self) -> None:
        """Chronicle should use the provided store backend."""
        custom_store = InMemoryChronicleStore()
        memory = Chronicle(store=custom_store)
        memory.remember("custom fact")
        assert custom_store.count() == 1
