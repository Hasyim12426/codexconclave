# Example 01: Research Team Conclave

Demonstrates a two-Arbiter Conclave where a **Research Specialist**
gathers information and a **Content Writer** transforms it into a
finished blog post.

## What This Shows

- Defining multiple `Arbiter` instances with distinct roles and personas
- Creating sequential `Directive` objects with context linking
- How the writer automatically receives the researcher's output
- `Protocol.sequential` execution order

## Prerequisites

```bash
pip install codexconclave
export OPENAI_API_KEY=your-key
```

## Run

```bash
python main.py
```

To use a different model:

```bash
CODEX_MODEL=claude-3-5-sonnet-20241022 python main.py
CODEX_MODEL=groq/llama-3.3-70b-versatile python main.py
```

## Expected Output

The script prints a structured research report followed by a polished
600-word blog post about quantum computing breakthroughs.

## Key Concepts

```python
# Context linking: writer receives researcher's output
writing_directive = Directive(
    description="Write a blog post based on the research...",
    arbiter=writer,
    context=[research_directive],  # <-- this is the key line
)
```

When `context` is set, the Conclave injects the prior directive's
output as additional context into the writer's LLM prompt.
