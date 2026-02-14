"""Example 03: Cascade Data Analysis Pipeline

Demonstrates an event-driven Cascade pipeline that ingests raw data,
cleans it, analyses it, and produces a formatted report.

No LLM calls are made — this example shows pure Python logic orchestrated
by the Cascade @initiate / @observe / @route decorators.

Run:
    python main.py
"""
from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import Field

from codexconclave.cascade.decorators import initiate, observe, route
from codexconclave.cascade.pipeline import Cascade, CascadeResult
from codexconclave.cascade.state import CascadeState

logging.basicConfig(
    level=os.getenv("CODEX_LOG_LEVEL", "INFO"),
    format="%(levelname)s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Raw data (simulated dataset)
# ---------------------------------------------------------------------------

RAW_RECORDS = [
    {"student": "Alice", "score": 92, "subject": "Math"},
    {"student": "Bob", "score": None, "subject": "Math"},  # missing
    {"student": "Carol", "score": 87, "subject": "Science"},
    {"student": "Dave", "score": 95, "subject": "Math"},
    {"student": "Eve", "score": -5, "subject": "Science"},   # invalid
    {"student": "Frank", "score": 78, "subject": "Science"},
    {"student": "Grace", "score": 101, "subject": "Math"},   # invalid
    {"student": "Hank", "score": 84, "subject": "Science"},
]


# ---------------------------------------------------------------------------
# Typed pipeline state
# ---------------------------------------------------------------------------


class AnalysisState(CascadeState):
    """State flowing through the data analysis pipeline."""

    raw_records: list[dict[str, Any]] = Field(default_factory=list)
    cleaned_records: list[dict[str, Any]] = Field(default_factory=list)
    removed_count: int = 0
    subject_stats: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )
    top_students: list[str] = Field(default_factory=list)
    has_outliers: bool = False
    report: str = ""


# ---------------------------------------------------------------------------
# Pipeline definition
# ---------------------------------------------------------------------------


class DataAnalysisPipeline(Cascade):
    """End-to-end data analysis from ingestion to report."""

    state: AnalysisState = AnalysisState()

    @initiate
    def ingest(self) -> list[dict[str, Any]]:
        """Load raw records into state."""
        self.state.raw_records = RAW_RECORDS
        logger.info("Ingested %d raw records.", len(RAW_RECORDS))
        return self.state.raw_records

    @observe(ingest)
    def clean(
        self, raw_records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Remove records with missing or out-of-range scores."""
        valid = [
            r for r in raw_records
            if r.get("score") is not None
            and 0 <= r["score"] <= 100
        ]
        removed = len(raw_records) - len(valid)
        self.state.cleaned_records = valid
        self.state.removed_count = removed
        logger.info(
            "Cleaned data: kept %d/%d records (%d removed).",
            len(valid),
            len(raw_records),
            removed,
        )
        return valid

    @observe(clean)
    def compute_stats(
        self, cleaned_records: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Compute per-subject statistics."""
        subjects: dict[str, list[int]] = {}
        for record in cleaned_records:
            subj = record["subject"]
            subjects.setdefault(subj, []).append(record["score"])

        stats: dict[str, dict[str, Any]] = {}
        for subj, scores in subjects.items():
            stats[subj] = {
                "count": len(scores),
                "average": round(sum(scores) / len(scores), 1),
                "highest": max(scores),
                "lowest": min(scores),
            }

        self.state.subject_stats = stats
        logger.info("Computed stats for %d subjects.", len(stats))
        return stats

    @observe(clean)
    def identify_top_students(
        self, cleaned_records: list[dict[str, Any]]
    ) -> list[str]:
        """Identify students scoring 90 or above."""
        top = [
            r["student"]
            for r in cleaned_records
            if r["score"] >= 90
        ]
        self.state.top_students = top
        logger.info("Found %d top students.", len(top))
        return top

    @observe(clean)
    def check_for_outliers(
        self, cleaned_records: list[dict[str, Any]]
    ) -> bool:
        """Flag if any records were removed as outliers."""
        self.state.has_outliers = self.state.removed_count > 0
        logger.info(
            "Outlier check: has_outliers=%s",
            self.state.has_outliers,
        )
        return self.state.has_outliers

    @observe(identify_top_students)
    @route
    def decide_report_type(self, top_students: list) -> str:
        """Route to detailed or standard report based on data quality.

        Observes ``identify_top_students`` which runs after
        ``compute_stats`` and ``check_for_outliers`` have already
        populated the shared state, ensuring the report has all data.
        """
        if self.state.has_outliers:
            return "generate_detailed_report"
        return "generate_standard_report"

    def generate_detailed_report(self) -> str:
        """Generate a report that includes data quality notes."""
        return self._build_report(include_quality_section=True)

    def generate_standard_report(self) -> str:
        """Generate a standard report without quality notes."""
        return self._build_report(include_quality_section=False)

    def _build_report(
        self, include_quality_section: bool
    ) -> str:
        """Build the final formatted report string."""
        lines: list[str] = [
            "=" * 50,
            "STUDENT PERFORMANCE REPORT",
            "=" * 50,
        ]

        for subject, stats in self.state.subject_stats.items():
            lines += [
                f"\n{subject.upper()}",
                f"  Students:   {stats['count']}",
                f"  Average:    {stats['average']}",
                f"  Highest:    {stats['highest']}",
                f"  Lowest:     {stats['lowest']}",
            ]

        if self.state.top_students:
            lines += [
                "\nTOP PERFORMERS (score ≥ 90)",
                "  " + ", ".join(self.state.top_students),
            ]
        else:
            lines.append("\nNo top performers this cycle.")

        if include_quality_section:
            lines += [
                "\nDATA QUALITY NOTES",
                f"  {self.state.removed_count} record(s) were removed "
                "due to missing or out-of-range scores.",
            ]

        lines.append("=" * 50)
        report = "\n".join(lines)
        self.state.report = report
        return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the pipeline and display the report."""
    logger.info("Starting Data Analysis Pipeline...")

    pipeline = DataAnalysisPipeline()
    result: CascadeResult = pipeline.execute()

    print("\n" + pipeline.state.report)
    print(
        f"\nPipeline completed {len(result.completed_methods)} "
        f"method(s) in {result.execution_time_ms:.1f}ms."
    )


if __name__ == "__main__":
    main()
