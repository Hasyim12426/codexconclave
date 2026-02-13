# Example 05: Hierarchical Conclave

Demonstrates `Protocol.hierarchical` — a manager Arbiter coordinates
specialist Arbiters, assigning Directives to the most appropriate
team member.

## What This Shows

- `Protocol.hierarchical` execution strategy
- Manager Arbiter that delegates and coordinates
- Three specialist Arbiters with distinct roles
- Directives with cross-directive context dependencies
- The manager synthesising specialist outputs

## The Team

| Arbiter | Role |
|---------|------|
| Project Manager | Coordinator (manager) |
| Market Research Specialist | Analyses competition |
| Product Copywriter | Crafts messaging |
| Go-to-Market Strategist | Plans the launch |

## Prerequisites

```bash
pip install codexconclave
export OPENAI_API_KEY=your-key
```

## Run

```bash
python main.py
```

## Key Concepts

```python
# Create the manager
project_manager = Arbiter(
    role="Product Launch Manager",
    objective="Coordinate the team...",
    allow_delegation=True,
)

# Use hierarchical protocol with a manager
conclave = Conclave(
    arbiters=[researcher, writer, strategist],
    directives=[analysis, messaging, launch_plan],
    protocol=Protocol.hierarchical,    # <-- key setting
    manager_arbiter=project_manager,   # <-- manager
)
```

In hierarchical mode, the manager LLM decides which specialist
handles each directive. Specialists do not need to be pre-assigned
in the `Directive` objects.

## When to Use Hierarchical Mode

- When you have specialists with clearly different domains
- When a manager needs to review and refine outputs
- When directive assignment should be dynamic and LLM-driven

For simpler pipelines where task order and assignment are known
upfront, `Protocol.sequential` is more efficient.
