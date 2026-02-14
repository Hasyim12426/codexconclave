"""Example 01: Research Team Conclave

A two-Arbiter Conclave where a Research Specialist gathers information
and a Content Writer transforms it into a finished deliverable.

The writer receives the researcher's output as context, demonstrating
how sequential Directives share information.

Requirements:
    pip install codexconclave
    export OPENAI_API_KEY=your-key   # or any supported provider

Run:
    python main.py

Set CODEX_MODEL to use a different model:
    CODEX_MODEL=claude-3-5-sonnet-20241022 python main.py
"""
from __future__ import annotations

import logging
import os

from codexconclave import Arbiter, Conclave, Directive, Protocol
from codexconclave.llm import LLMProvider

logging.basicConfig(
    level=os.getenv("CODEX_LOG_LEVEL", "INFO"),
    format="%(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def build_research_conclave() -> Conclave:
    """Construct a researcher + writer Conclave.

    Returns:
        Conclave: Ready-to-execute team.
    """
    model = os.getenv("CODEX_MODEL", "gpt-4o")
    llm = LLMProvider(model=model, temperature=0.7)

    researcher = Arbiter(
        role="Research Specialist",
        objective=(
            "Gather comprehensive, accurate information on any topic "
            "using all available context"
        ),
        persona=(
            "A methodical researcher with deep expertise in synthesizing "
            "complex information from multiple angles"
        ),
        llm=llm,
        verbose=True,
    )

    writer = Arbiter(
        role="Content Writer",
        objective=(
            "Transform raw research into clear, compelling, "
            "well-structured written content"
        ),
        persona=(
            "An experienced writer skilled at making technical topics "
            "accessible and engaging for diverse audiences"
        ),
        llm=llm,
        verbose=True,
    )

    research_directive = Directive(
        description=(
            "Research the top 5 recent breakthroughs in quantum "
            "computing (2023–2024). For each breakthrough, include: "
            "the organization involved, a technical summary, and the "
            "practical real-world implications."
        ),
        expected_output=(
            "A structured report with 5 numbered entries. Each entry "
            "must contain: title, organization, technical summary "
            "(2–3 sentences), and real-world impact (1–2 sentences)."
        ),
        arbiter=researcher,
    )

    writing_directive = Directive(
        description=(
            "Using the provided research, write a 600-word blog post "
            "titled 'The Quantum Leap: 5 Breakthroughs Reshaping "
            "Computing in 2024'. Write for a technically literate "
            "general audience — explain concepts without condescension."
        ),
        expected_output=(
            "A polished blog post with: an engaging introduction, "
            "one paragraph per breakthrough, and a forward-looking "
            "conclusion. Include a brief callout for the most "
            "impactful breakthrough."
        ),
        arbiter=writer,
        context=[research_directive],
    )

    return Conclave(
        arbiters=[researcher, writer],
        directives=[research_directive, writing_directive],
        protocol=Protocol.sequential,
        verbose=True,
    )


def main() -> None:
    """Run the research team and print the final blog post."""
    logger.info("Starting Research Team Conclave...")

    conclave = build_research_conclave()
    result = conclave.assemble()

    print("\n" + "=" * 60)
    print("RESEARCH TEAM OUTPUT")
    print("=" * 60)
    print(result.final_output)
    print("=" * 60)
    print(
        f"\nCompleted {len(result.directive_results)} directive(s)."
    )


if __name__ == "__main__":
    main()
