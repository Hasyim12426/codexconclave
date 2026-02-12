# Example 04: Memory-Enabled Conclave

Demonstrates the **Chronicle** memory system — how Arbiters store and
recall information to build persistent context across interactions.

## What This Shows

- `Chronicle.remember()` — store a memory entry
- `Chronicle.recall()` — retrieve semantically relevant entries
- `Chronicle.summarize_context()` — format recalled memories for LLM prompts
- `Chronicle.clear()` — reset the memory store
- Sharing a `ChronicleStore` between multiple Arbiter instances

## Prerequisites

```bash
pip install codexconclave
```

No API keys required — this example uses only the in-memory store.

## Run

```bash
python main.py
```

## Expected Output

```
═══════════════════════════════════════════════════════
CHRONICLE MEMORY DEMONSTRATION
═══════════════════════════════════════════════════════

── Storing facts into Chronicle ──
  Stored [a1b2c3d4]: The user is researching quantum computing.
  ...

Chronicle now holds 5 entries.

── Recall: 'What are the user's preferences?' ──
  [e5f6a7b8] Jordan prefers concise answers with bullet points.
  ...
```

## How Chronicle Works

```python
from codexconclave.chronicle.memory import Chronicle

chronicle = Chronicle(arbiter_role="My Arbiter")

# Store a fact
chronicle.remember("The project deadline is June 15th.")

# Recall relevant context
entries = chronicle.recall("deadline", limit=3)
for entry in entries:
    print(entry.content)

# Get a formatted string for LLM prompts
context = chronicle.summarize_context("project schedule")
```

## Advanced: Persistent Storage

Replace `InMemoryChronicleStore` with a persistent backend:

```python
# Install: pip install "codexconclave[memory]"
from codexconclave.chronicle.store import LanceDBChronicleStore

store = LanceDBChronicleStore(path="./my_memory")
chronicle = Chronicle(store=store, arbiter_role="Analyst")
```

LanceDB stores are persisted to disk and survive process restarts.
