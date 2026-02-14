"""Example 02: Custom Instruments

Demonstrates building custom instruments (tools) and attaching them
to an Arbiter.  All data is simulated so the example runs without
any external API calls or dependencies beyond codexconclave.

Run:
    python main.py

Set CODEX_MODEL to use a specific LLM:
    CODEX_MODEL=gpt-4o python main.py
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

from codexconclave import Arbiter, Conclave, Directive, Protocol
from codexconclave.instruments import StructuredInstrument
from codexconclave.instruments.base import BaseInstrument
from codexconclave.llm import LLMProvider

logging.basicConfig(
    level=os.getenv("CODEX_LOG_LEVEL", "INFO"),
    format="%(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Simulated data store
# ---------------------------------------------------------------------------

_WEATHER_DB: dict[str, dict[str, Any]] = {
    "london": {"temp_c": 14, "humidity": 72, "condition": "Cloudy"},
    "new york": {"temp_c": 18, "humidity": 60, "condition": "Partly Sunny"},
    "tokyo": {"temp_c": 22, "humidity": 55, "condition": "Clear"},
    "sydney": {"temp_c": 25, "humidity": 65, "condition": "Sunny"},
    "paris": {"temp_c": 16, "humidity": 68, "condition": "Overcast"},
}

_NEWS_FEED: list[dict[str, str]] = [
    {
        "headline": "Tech giant unveils next-gen AI chip with 3x throughput",
        "category": "technology",
        "date": "2026-04-04",
    },
    {
        "headline": "Renewable energy hits 40% of global grid for first time",
        "category": "environment",
        "date": "2026-04-03",
    },
    {
        "headline": "Quantum error correction milestone reached by research team",
        "category": "science",
        "date": "2026-04-02",
    },
    {
        "headline": "Global markets rally on positive economic data",
        "category": "finance",
        "date": "2026-04-04",
    },
]


# ---------------------------------------------------------------------------
# Instruments built with StructuredInstrument.from_function
# ---------------------------------------------------------------------------


def get_weather(city: str, units: str = "celsius") -> str:
    """Retrieve current weather conditions for a given city.

    Args:
        city: City name (case-insensitive).
        units: Temperature unit — 'celsius' or 'fahrenheit'.

    Returns:
        str: Formatted weather report.
    """
    data = _WEATHER_DB.get(city.lower())
    if data is None:
        available = ", ".join(_WEATHER_DB)
        return (
            f"City '{city}' not found. "
            f"Available cities: {available}."
        )

    temp = data["temp_c"]
    if units == "fahrenheit":
        temp = round(temp * 9 / 5 + 32, 1)
        unit_label = "°F"
    else:
        unit_label = "°C"

    return (
        f"{city.title()}: {temp}{unit_label}, "
        f"Humidity {data['humidity']}%, "
        f"Condition: {data['condition']}"
    )


def fetch_news(
    category: str = "all",
    max_results: int = 3,
) -> str:
    """Fetch recent news headlines, optionally filtered by category.

    Args:
        category: Category filter ('technology', 'science',
            'environment', 'finance', or 'all').
        max_results: Maximum number of headlines to return.

    Returns:
        str: Newline-separated headlines with dates.
    """
    articles = _NEWS_FEED
    if category != "all":
        articles = [
            a for a in articles if a["category"] == category
        ]

    selected = articles[:max_results]
    if not selected:
        return f"No news found for category '{category}'."

    lines = [
        f"[{a['date']}] {a['headline']}" for a in selected
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Custom instrument via subclassing
# ---------------------------------------------------------------------------


class DataSummaryInstrument(BaseInstrument):
    """Summarise a JSON list of city weather records.

    Computes average temperature and lists all conditions.
    """

    name: str = "summarise_weather_data"
    description: str = (
        "Compute a statistical summary of weather data for "
        "multiple cities. Pass a JSON array of city names."
    )

    def execute(self, cities_json: str = "[]") -> str:
        """Summarise weather for a list of cities.

        Args:
            cities_json: JSON-encoded list of city name strings.

        Returns:
            str: Summary statistics.
        """
        try:
            cities: list[str] = json.loads(cities_json)
        except json.JSONDecodeError:
            return "Invalid JSON: expected a list of city names."

        records = []
        for city in cities:
            data = _WEATHER_DB.get(city.lower())
            if data:
                records.append((city.title(), data["temp_c"]))

        if not records:
            return "No matching cities found."

        avg_temp = sum(t for _, t in records) / len(records)
        city_list = ", ".join(f"{c} ({t}°C)" for c, t in records)
        return (
            f"Summary for {len(records)} cities: {city_list}. "
            f"Average temperature: {avg_temp:.1f}°C."
        )


# ---------------------------------------------------------------------------
# Build the Conclave
# ---------------------------------------------------------------------------


def build_weather_conclave() -> Conclave:
    """Build a Conclave equipped with weather and news instruments."""
    model = os.getenv("CODEX_MODEL", "gpt-4o")
    llm = LLMProvider(model=model, temperature=0.5)

    weather_tool = StructuredInstrument.from_function(get_weather)
    news_tool = StructuredInstrument.from_function(fetch_news)
    summary_tool = DataSummaryInstrument()

    analyst = Arbiter(
        role="Weather & News Analyst",
        objective=(
            "Retrieve weather and news data using instruments, "
            "then synthesise an insightful briefing"
        ),
        persona=(
            "A data-driven analyst who combines multiple information "
            "sources to produce actionable summaries"
        ),
        llm=llm,
        instruments=[weather_tool, news_tool, summary_tool],
        verbose=True,
    )

    briefing_directive = Directive(
        description=(
            "Prepare a morning briefing that includes: "
            "(1) weather for London, Tokyo, and New York, "
            "(2) the top 2 technology news stories, "
            "(3) a weather summary across all 3 cities."
        ),
        expected_output=(
            "A concise morning briefing with three clearly "
            "labelled sections: Weather, Tech News, and Summary."
        ),
        arbiter=analyst,
    )

    return Conclave(
        arbiters=[analyst],
        directives=[briefing_directive],
        protocol=Protocol.sequential,
    )


def main() -> None:
    """Run the instrument demo and print the briefing."""
    logger.info("Starting Custom Instruments example...")

    conclave = build_weather_conclave()
    result = conclave.assemble()

    print("\n" + "=" * 60)
    print("MORNING BRIEFING")
    print("=" * 60)
    print(result.final_output)
    print("=" * 60)


if __name__ == "__main__":
    main()
