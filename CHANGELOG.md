# Changelog

All notable changes to CodexConclave are documented here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-04-04

### Added

#### Core Execution
- `Conclave` orchestrator with `sequential` and `hierarchical` protocols
- `Arbiter` autonomous agent with full LLM ↔ tool calling loop
- `Directive` task definition with context linking, guardrails, and output
  file writing
- `Protocol` enum with `sequential` and `hierarchical` variants
- `ConclaveResult`, `DirectiveResult`, `ArbiterResult` typed result models
- Arbiter delegation support (`allow_delegation=True`) for peer-to-peer
  task handoff within a Conclave
- Iteration limit and wall-clock time limit enforcement in Arbiter
- Automatic round-robin Arbiter assignment for unassigned Directives
- Retry logic (`max_retries`) for failed Directive executions

#### Cascade Pipelines
- `Cascade` base class for event-driven pipeline workflows
- `@initiate` decorator to mark pipeline entry points
- `@observe` decorator to register method dependencies
- `@route` decorator to conditionally branch execution
- `and_()` / `or_()` combinators for multi-dependency `@observe` rules
- `CascadeState` typed state base class (Pydantic model)
- `UnstructuredCascadeState` for flexible dict-based state
- `CascadeResult` with run ID, completed methods, and final state

#### LLM Integration
- `LLMProvider` unified interface wrapping `litellm`
- Support for OpenAI, Anthropic Claude, Google Gemini, AWS Bedrock,
  Azure OpenAI, Groq, Mistral, and DeepSeek
- Model registry with context window sizes for 25+ models
- Automatic retry with exponential backoff on transient LLM errors
- Streaming support via `stream()` method
- Async completion via `acomplete()`
- Token counting with `tiktoken` (with word-count fallback)
- `LLMCallSignal` emitted after each completion for observability

#### Instruments (Tools)
- `BaseInstrument` abstract base with caching, use limits, and
  signal emission
- `StructuredInstrument.from_function()` factory to wrap Python callables
- Automatic JSON schema inference from function type annotations
  (resolves `from __future__ import annotations` string annotations)
- `args_schema` Pydantic model validation for structured inputs
- `InstrumentResult` typed result with execution time and cache flag
- `max_uses` limit enforcement with `InstrumentUsageLimitError`

#### Memory (Chronicle)
- `Chronicle` unified memory interface
- `BaseChronicleStore` abstract storage backend
- `InMemoryChronicleStore` lightweight in-memory implementation
- `ChronicleEntry` typed memory record with metadata and scoring

#### Observability
- `SignalBus` thread-safe singleton event bus with per-context override
- Typed signal hierarchy: Arbiter, Directive, Conclave, Cascade,
  Instrument, and LLM call signals
- `BaseSignalListener` abstract listener with type-based filtering
- `ObservabilityTracker` with OpenTelemetry OTLP export
- Graceful degradation when `OTEL_SDK_DISABLED=true`

#### CLI
- `codex create conclave <name>` — scaffold a new Conclave project
- `codex create cascade <name>` — scaffold a new Cascade project
- `codex run` — execute the project in the current directory
- `codex chat <topic>` — start an interactive chat session

#### Developer Experience
- Comprehensive test suite (196 tests, 70% coverage)
- `pyproject.toml`-based project configuration with hatchling
- Optional dependency extras: `[memory]`, `[knowledge]`, `[all]`
- `.env.example` for all supported environment variables
- 5 complete runnable examples with individual READMEs

[Unreleased]: https://github.com/codexconclave/codexconclave/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/codexconclave/codexconclave/releases/tag/v1.0.0
