# Building Custom Instruments

Instruments are the tools that Arbiters can call during execution.
This guide covers all ways to create and use instruments.

---

## Quick Start: Wrapping a Function

The fastest way to create an instrument is `StructuredInstrument.from_function`:

```python
from codexconclave.instruments import StructuredInstrument

def search_wikipedia(topic: str, max_sentences: int = 3) -> str:
    """Search Wikipedia and return a summary for the given topic."""
    # your implementation here
    return f"Wikipedia summary for {topic} ({max_sentences} sentences)"

instrument = StructuredInstrument.from_function(search_wikipedia)
```

The function's name, docstring, and type annotations are used to build
the instrument's name, description, and JSON schema automatically.

---

## Custom Instrument via Subclassing

For full control, subclass `BaseInstrument`:

```python
from codexconclave.instruments.base import BaseInstrument
from pydantic import Field


class SQLQueryInstrument(BaseInstrument):
    """Execute read-only SQL queries against a database."""

    name: str = "sql_query"
    description: str = (
        "Execute a read-only SQL SELECT query and return "
        "the results as formatted text."
    )
    connection_string: str = Field(
        description="Database connection string"
    )
    max_rows: int = 100

    def execute(self, query: str) -> str:
        """Run the query and return results.

        Args:
            query: A SQL SELECT statement.

        Returns:
            str: Formatted query results or an error message.
        """
        if not query.strip().upper().startswith("SELECT"):
            raise ValueError(
                "Only SELECT queries are permitted."
            )
        # Connect and execute ...
        return f"Results for: {query}"
```

---

## Instrument Schema

Instruments expose a JSON schema for LLM function calling.
`BaseInstrument.schema()` returns an OpenAI-compatible tool schema:

```python
instrument.schema()
# {
#   "type": "function",
#   "function": {
#     "name": "sql_query",
#     "description": "Execute a read-only SQL SELECT query...",
#     "parameters": {
#       "type": "object",
#       "properties": {
#         "query": {"type": "string"}
#       },
#       "required": ["query"]
#     }
#   }
# }
```

Override `_parameters_schema()` in your subclass for precise control.

---

## Caching

Enable result caching to avoid redundant calls:

```python
instrument = StructuredInstrument.from_function(
    expensive_api_call,
    cache_enabled=True,
    cache_ttl=3600,  # 1 hour
)
```

Results are cached by a hash of the input kwargs. The cache is
in-memory and per-instrument-instance.

---

## Usage Limits

Prevent excessive calls with `max_uses`:

```python
instrument = StructuredInstrument.from_function(
    rate_limited_api,
    max_uses=10,
)
```

After 10 calls, `InstrumentUsageLimitError` is raised.

---

## Async Instruments

Override `aexecute()` for native async support:

```python
import asyncio
from codexconclave.instruments.base import BaseInstrument


class AsyncWebFetcher(BaseInstrument):
    name: str = "fetch_url"
    description: str = "Fetch the contents of a URL asynchronously."

    def execute(self, url: str) -> str:
        return asyncio.run(self.aexecute(url=url))

    async def aexecute(self, url: str) -> str:  # type: ignore[override]
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=30)
            return response.text[:2000]
```

---

## Attaching Instruments to Arbiters

```python
from codexconclave import Arbiter
from codexconclave.llm import LLMProvider

arbiter = Arbiter(
    role="Data Analyst",
    objective="Analyse data using available instruments",
    llm=LLMProvider(model="gpt-4o"),
    instruments=[sql_query_instrument, search_instrument],
)
```

Instruments can also be scoped to a single `Directive`:

```python
from codexconclave import Directive

directive = Directive(
    description="Fetch and summarize the latest news",
    expected_output="A 3-bullet news summary",
    instruments=[news_fetcher_instrument],  # only for this directive
)
```

---

## Input Validation with `args_schema`

Use a Pydantic model to validate inputs before execution:

```python
from pydantic import BaseModel, Field


class QueryArgs(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    limit: int = Field(default=10, ge=1, le=100)


instrument = StructuredInstrument(
    name="db_search",
    description="Search the database",
    func=my_search_function,
    args_schema=QueryArgs,
)
```

Invalid inputs raise `InstrumentValidationError` before the function runs.

---

## Observing Instrument Use

Every instrument execution emits an `InstrumentUsedSignal`:

```python
from codexconclave.signals.bus import SignalBus
from codexconclave.signals.listener import BaseSignalListener
from codexconclave.signals.types import InstrumentUsedSignal, Signal


class InstrumentLogger(BaseSignalListener):
    def handle(self, signal: Signal) -> None:
        if isinstance(signal, InstrumentUsedSignal):
            print(
                f"Instrument '{signal.instrument_name}' used "
                f"(cached={signal.cached})"
            )


SignalBus.instance().register(InstrumentLogger())
```
