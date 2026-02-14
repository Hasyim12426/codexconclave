"""Example 04: Memory-Enabled Conclave

Demonstrates Chronicle memory — how an Arbiter stores and recalls
information across multiple interactions.

This example builds a simple interview simulation where the Arbiter
remembers facts stated in earlier messages.

No external dependencies beyond codexconclave.

Run:
    python main.py
"""
from __future__ import annotations

import logging
import os

from codexconclave.chronicle.memory import Chronicle
from codexconclave.chronicle.store import ChronicleEntry, InMemoryChronicleStore

logging.basicConfig(
    level=os.getenv("CODEX_LOG_LEVEL", "INFO"),
    format="%(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def demonstrate_chronicle_memory() -> None:
    """Show Chronicle's remember / recall cycle."""
    store = InMemoryChronicleStore()
    chronicle = Chronicle(
        store=store,
        arbiter_role="Research Assistant",
    )

    # ── Stage 1: Store facts ─────────────────────────────────────────
    print("\n── Storing facts into Chronicle ──")
    facts = [
        "The user is researching quantum computing.",
        "The user's name is Jordan.",
        "Jordan prefers concise answers with bullet points.",
        "Jordan works at a university research lab.",
        "Previous session covered quantum entanglement.",
    ]
    for fact in facts:
        entry = chronicle.remember(fact)
        print(f"  Stored [{entry.id[:8]}]: {fact}")

    print(f"\nChronicle now holds {len(chronicle)} entries.")

    # ── Stage 2: Recall relevant context ────────────────────────────
    queries = [
        "What are the user's preferences?",
        "What is the user working on?",
        "quantum entanglement",
    ]

    for query in queries:
        print(f"\n── Recall: '{query}' ──")
        recalled = chronicle.recall(query, limit=3)
        if recalled:
            for entry in recalled:
                print(f"  [{entry.id[:8]}] {entry.content}")
        else:
            print("  (no matching entries)")

    # ── Stage 3: Summarise context for an LLM prompt ────────────────
    print("\n── Context summary for 'user preferences' ──")
    summary = chronicle.summarize_context("user preferences")
    print(summary)

    # ── Stage 4: Clear and verify ───────────────────────────────────
    chronicle.clear()
    print(f"\nAfter clear: {len(chronicle)} entries remaining.")


def demonstrate_cross_session_memory() -> None:
    """Simulate a shared Chronicle across two Arbiter instances."""
    shared_store = InMemoryChronicleStore()

    # First Arbiter stores findings
    arbiter_a = Chronicle(
        store=shared_store,
        arbiter_role="Researcher",
    )
    arbiter_a.remember(
        "Found that LLM context windows have grown 100x since 2020."
    )
    arbiter_a.remember(
        "GPT-4o supports 128K tokens; Gemini 1.5 Pro supports 2M."
    )

    # Second Arbiter retrieves from the same store
    arbiter_b = Chronicle(
        store=shared_store,
        arbiter_role="Writer",
    )
    recalled = arbiter_b.recall("context window size", limit=2)
    print("\n── Shared memory: Writer recalls Researcher's findings ──")
    for entry in recalled:
        print(f"  {entry.content}")


def main() -> None:
    """Run all Chronicle memory demonstrations."""
    print("=" * 55)
    print("CHRONICLE MEMORY DEMONSTRATION")
    print("=" * 55)

    demonstrate_chronicle_memory()
    demonstrate_cross_session_memory()

    print("\n" + "=" * 55)
    print("Done.")


if __name__ == "__main__":
    main()
