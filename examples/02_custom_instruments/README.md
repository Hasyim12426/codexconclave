# Example 02: Custom Instruments

Demonstrates two ways to build custom instruments (tools) and use
them with an Arbiter.

## What This Shows

- `StructuredInstrument.from_function()` — wrap any Python function
- `BaseInstrument` subclassing — full control over schema and logic
- Attaching instruments to an Arbiter
- The Arbiter autonomously choosing which instruments to call

## Instruments in This Example

| Instrument | Source | What It Does |
|------------|--------|-------------|
| `get_weather` | `from_function` | Returns weather for a city |
| `fetch_news` | `from_function` | Returns headlines by category |
| `DataSummaryInstrument` | Subclass | Averages temperatures for cities |

## Prerequisites

```bash
pip install codexconclave
export OPENAI_API_KEY=your-key
```

## Run

```bash
python main.py
```

No external APIs are used — all data is simulated.

## Key Concepts

```python
# Wrap a function as an instrument
weather_tool = StructuredInstrument.from_function(get_weather)

# Subclass for full control
class DataSummaryInstrument(BaseInstrument):
    name = "summarise_weather_data"
    description = "Compute statistics for multiple cities"
    
    def execute(self, cities_json: str) -> str:
        ...

# Attach instruments to an Arbiter
analyst = Arbiter(
    role="Analyst",
    instruments=[weather_tool, news_tool, summary_tool],
)
```

The Arbiter will automatically call the right instruments based on
the Directive description — you do not need to specify which tools
to use.
