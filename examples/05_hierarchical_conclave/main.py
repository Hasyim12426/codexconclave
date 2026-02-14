"""Example 05: Hierarchical Conclave

Demonstrates the hierarchical Protocol where a manager Arbiter
coordinates specialist Arbiters, delegating work and gathering results.

Run:
    python main.py

Requires:
    export OPENAI_API_KEY=your-key
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


def build_product_launch_conclave() -> Conclave:
    """Build a product launch Conclave with a coordinator and specialists.

    The manager Arbiter assigns each directive to the most appropriate
    specialist and reviews outputs before finalising.

    Returns:
        Conclave: Configured hierarchical Conclave.
    """
    model = os.getenv("CODEX_MODEL", "gpt-4o")
    llm = LLMProvider(model=model, temperature=0.7)

    # ── Specialist Arbiters ──────────────────────────────────────────

    market_researcher = Arbiter(
        role="Market Research Specialist",
        objective=(
            "Analyse market trends and competitive landscapes to "
            "provide data-driven insights for product decisions"
        ),
        persona=(
            "A rigorous market analyst with deep expertise in "
            "technology sector trends and consumer behaviour"
        ),
        llm=llm,
    )

    copywriter = Arbiter(
        role="Product Copywriter",
        objective=(
            "Craft compelling, benefit-focused product messaging "
            "that resonates with target audiences"
        ),
        persona=(
            "A creative copywriter who translates complex product "
            "features into clear, compelling language"
        ),
        llm=llm,
    )

    launch_strategist = Arbiter(
        role="Go-to-Market Strategist",
        objective=(
            "Design effective launch strategies including channel "
            "selection, timing, and success metrics"
        ),
        persona=(
            "A strategic thinker with experience launching B2B SaaS "
            "products to enterprise and SMB markets"
        ),
        llm=llm,
    )

    # ── Manager Arbiter ──────────────────────────────────────────────

    project_manager = Arbiter(
        role="Product Launch Manager",
        objective=(
            "Coordinate the product launch team, assign work to the "
            "right specialists, and synthesise outputs into a cohesive "
            "launch plan"
        ),
        persona=(
            "An experienced product manager who excels at cross-functional "
            "coordination and keeping projects aligned with business goals"
        ),
        llm=llm,
        allow_delegation=True,
        verbose=True,
    )

    # ── Directives ──────────────────────────────────────────────────

    market_analysis_directive = Directive(
        description=(
            "Analyse the current AI-powered productivity tools market. "
            "Identify the top 3 competitors, their pricing, and the "
            "key gaps our new tool could fill."
        ),
        expected_output=(
            "A competitive analysis report with: "
            "(1) top 3 competitors and their positioning, "
            "(2) pricing comparison table, "
            "(3) identified market gaps."
        ),
    )

    messaging_directive = Directive(
        description=(
            "Create product messaging for our new AI productivity tool. "
            "Include a tagline, value proposition statement, and 3 "
            "key benefit statements for our website hero section."
        ),
        expected_output=(
            "A messaging document with: tagline (≤10 words), "
            "value proposition (2 sentences), "
            "3 benefit statements (1 sentence each)."
        ),
        context=[market_analysis_directive],
    )

    launch_plan_directive = Directive(
        description=(
            "Design a 30-day product launch plan. Include launch channels, "
            "weekly milestones, and 3 KPIs to track success in the first "
            "month."
        ),
        expected_output=(
            "A structured 30-day launch plan with: "
            "recommended channels, week-by-week milestones, "
            "and 3 measurable KPIs."
        ),
        context=[market_analysis_directive, messaging_directive],
    )

    return Conclave(
        arbiters=[
            market_researcher,
            copywriter,
            launch_strategist,
        ],
        directives=[
            market_analysis_directive,
            messaging_directive,
            launch_plan_directive,
        ],
        protocol=Protocol.hierarchical,
        manager_arbiter=project_manager,
        verbose=True,
    )


def main() -> None:
    """Execute the hierarchical Conclave and display results."""
    logger.info("Starting Hierarchical Conclave...")

    conclave = build_product_launch_conclave()
    result = conclave.assemble()

    print("\n" + "=" * 60)
    print("PRODUCT LAUNCH PLAN")
    print("=" * 60)
    print(result.final_output)
    print("=" * 60)

    if len(result.directive_results) > 1:
        print("\nIntermediate outputs:")
        for i, dr in enumerate(result.directive_results[:-1], 1):
            print(f"\n[{i}] {dr.agent_role}")
            print(dr.output[:300] + ("..." if len(dr.output) > 300 else ""))


if __name__ == "__main__":
    main()
