# Architecture Guide

## Overview

CodexConclave provides two complementary execution models for building
AI agent workflows:

1. **Conclave** — teams of autonomous Arbiters collaborating on Directives
2. **Cascade** — explicit event-driven pipelines with typed state

Both models share a common infrastructure layer: `LLMProvider`,
`SignalBus`, `Chronicle`, and `Instruments`.

---

## System Diagram

```
┌──────────────────────────────────────────────────────────┐
│                         Conclave                         │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐  │
│  │ Arbiter 1  │  │ Arbiter 2  │  │     Arbiter N      │  │
│  │            │  │            │  │                    │  │
│  │ role       │  │ role       │  │  allow_delegation  │  │
│  │ objective  │  │ objective  │  │  max_iterations    │  │
│  │ persona    │  │ persona    │  │  instruments       │  │
│  └─────┬──────┘  └─────┬──────┘  └────────┬───────────┘  │
│        │               │                  │               │
│  ┌─────▼───────────────▼──────────────────▼───────────┐   │
│  │                    LLMProvider                      │   │
│  │         (litellm — unified provider interface)      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                           │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────────┐    │
│  │ Chronicle │  │  SignalBus   │  │  Observability   │    │
│  │ (Memory)  │  │  (Events)    │  │  Tracker (OTEL)  │    │
│  └───────────┘  └──────────────┘  └──────────────────┘    │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                         Cascade                          │
│                                                          │
│  @initiate ──► @observe ──► @observe ──► @route          │
│     start        fetch        clean      decide          │
│                                │                         │
│                           @observe ──► @observe          │
│                             report      summarize        │
│                                                          │
│  Shared CascadeState flows through the execution graph   │
└──────────────────────────────────────────────────────────┘
```

---

## Conclave Execution Flow

### Sequential Protocol

1. **Validation** — `Conclave._validate()` ensures all Directives have
   an assigned Arbiter (or auto-assigns from the Arbiters list).
2. **Signal emission** — `ConclaveStartedSignal` is emitted with counts.
3. **Directive loop** — for each Directive in order:
   a. Build a context string from all prior `DirectiveResult` outputs.
   b. Emit `DirectiveStartedSignal`.
   c. Call `arbiter.perform(directive, context=context)`.
   d. Apply guardrail if set; write output file if configured.
   e. Call `directive.mark_complete(result)` to store result and invoke callback.
   f. Emit `DirectiveCompletedSignal`.
4. **Result aggregation** — `ConclaveResult` is built from all results.
5. **Signal emission** — `ConclaveCompletedSignal` is emitted.

### Hierarchical Protocol

1. A manager `Arbiter` is created (from `manager_arbiter` or `manager_llm`).
2. The manager receives a summary of all Directives.
3. For each Directive, the manager decides which Arbiter should handle it
   via an LLM call that returns a JSON assignment.
4. The assigned Arbiter executes the Directive and returns the result.
5. The manager can optionally review and refine the output.
6. Results are aggregated into `ConclaveResult`.

---

## Arbiter Execution Loop

```
perform(directive, context)
│
├─ Build system prompt (role + objective + persona + instruments)
├─ Build user message (directive description + expected output + context)
│
└─ Loop (max_iterations times):
   │
   ├─ Check time limit (raise TimeoutError if exceeded)
   ├─ Call llm.complete(messages, tools=schemas)
   ├─ Check time limit again (after potentially slow LLM call)
   │
   ├─ If directive.output_format set → parse structured output → return
   │
   ├─ If response contains JSON instrument call:
   │   ├─ Execute the instrument
   │   ├─ Append assistant message + tool result to messages
   │   └─ Continue loop
   │
   ├─ If allow_delegation=True and response contains delegation JSON:
   │   ├─ Find peer Arbiter by role
   │   ├─ Delegate sub-directive to peer
   │   ├─ Append delegation result to messages
   │   └─ Continue loop
   │
   └─ Otherwise: treat response as final answer → return ArbiterResult
```

---

## Cascade Execution Flow

1. **Method registration** — `__init_subclass__` introspects decorated
   methods and builds `_initiate_methods`, `_observe_map`, `_route_methods`.
2. **Graph construction** — `_build_execution_graph()` produces a dict
   of `method_name → list[dependency_names]`.
3. **Topological execution**:
   a. All `@initiate` methods run first (in order).
   b. For each `@observe` method, check if all dependencies have completed.
   c. Enqueue newly-eligible methods and execute them.
   d. `@route` methods return a method name string; the named method is
      added to the execution queue.
4. **State updates** — each method receives its input from upstream outputs
   and may mutate `self.state`.
5. **Completion** — returns `CascadeResult` with run ID, completed
   method names, and a snapshot of the final state.

---

## Signal System

All lifecycle events are published through `SignalBus.instance()`:

```
SignalBus (singleton, thread-safe)
│
├── register(listener: BaseSignalListener)
├── unregister(listener: BaseSignalListener)
└── emit(signal: Signal)
    └── For each listener: if listener.accepts(signal) → listener.handle(signal)
```

Override `BaseSignalListener.accepts()` to filter to specific signal types.
Override `BaseSignalListener.handle()` to process the signal.

### Signal Hierarchy

```
Signal
├── ArbiterSignal
│   ├── ArbiterStartedSignal
│   ├── ArbiterCompletedSignal
│   └── ArbiterErrorSignal
├── DirectiveSignal
│   ├── DirectiveStartedSignal
│   ├── DirectiveCompletedSignal
│   └── DirectiveErrorSignal
├── ConclaveSignal
│   ├── ConclaveStartedSignal
│   ├── ConclaveCompletedSignal
│   └── ConclaveErrorSignal
├── InstrumentUsedSignal
├── LLMCallSignal
└── CascadeSignal
    ├── CascadeStartedSignal
    └── CascadeCompletedSignal
```

---

## Memory (Chronicle)

```
Chronicle
└── BaseChronicleStore (abstract)
    ├── InMemoryChronicleStore  ← default, no deps
    └── LanceDBChronicleStore   ← optional, persistent, vector search
```

The `Chronicle` class wraps any `BaseChronicleStore` and provides
`remember(content, metadata)` and `recall(query, limit)` as its
primary interface. Implement `BaseChronicleStore` to add new backends
(e.g. Qdrant, Chroma, Redis).

---

## Extension Points

| Component | How to Extend |
|-----------|---------------|
| Custom Instrument | Subclass `BaseInstrument`, implement `execute()` |
| Custom Memory Backend | Subclass `BaseChronicleStore`, implement `save/search/clear/count` |
| Custom Signal Listener | Subclass `BaseSignalListener`, implement `handle()` |
| Custom LLM Provider | Not needed — `LLMProvider` supports any litellm model string |
| Custom Arbiter | Subclass `BaseArbiter`, implement `perform()` |
