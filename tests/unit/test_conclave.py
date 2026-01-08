"""Unit tests for the Conclave orchestration class."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from codexconclave.arbiter.core import Arbiter
from codexconclave.conclave import (
    Conclave,
    ConclaveConfigError,
    ConclaveResult,
)
from codexconclave.directive import Directive
from codexconclave.protocol import Protocol

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_arbiter(role: str, llm: MagicMock) -> Arbiter:
    """Create an Arbiter with a mock LLM.

    Args:
        role: The arbiter role label.
        llm: Mock LLM provider.

    Returns:
        Arbiter: Configured test Arbiter.
    """
    return Arbiter(
        role=role,
        objective=f"Do {role} work.",
        llm=llm,
    )


def make_directive(description: str, arbiter: Arbiter) -> Directive:
    """Create a Directive assigned to an arbiter.

    Args:
        description: Directive description.
        arbiter: The assigned Arbiter.

    Returns:
        Directive: Configured test Directive.
    """
    return Directive(
        description=description,
        expected_output="A complete result.",
        arbiter=arbiter,
    )


# ---------------------------------------------------------------------------
# ConclaveResult tests
# ---------------------------------------------------------------------------


class TestConclaveResult:
    """Tests for the ConclaveResult model."""

    def test_str_returns_final_output(self) -> None:
        """str(ConclaveResult) should return final_output."""
        result = ConclaveResult(
            directive_results=[],
            final_output="The answer.",
        )
        assert str(result) == "The answer."

    def test_token_usage_defaults_empty(self) -> None:
        """token_usage should default to an empty dict."""
        result = ConclaveResult(directive_results=[], final_output="")
        assert result.token_usage == {}


# ---------------------------------------------------------------------------
# Conclave validation tests
# ---------------------------------------------------------------------------


class TestConclaveValidation:
    """Tests for Conclave pre-execution validation."""

    def test_no_directives_raises(self, mock_llm: MagicMock) -> None:
        """Conclave with no directives should raise ConclaveConfigError."""
        arbiter = make_mock_arbiter("R", mock_llm)
        c = Conclave(
            arbiters=[arbiter],
            directives=[],
        )
        with pytest.raises(ConclaveConfigError, match="Directive"):
            c.assemble()

    def test_no_arbiters_raises(self, mock_llm: MagicMock) -> None:
        """Conclave with no arbiters should raise ConclaveConfigError."""
        directive = Directive(description="D", expected_output="E")
        c = Conclave(
            arbiters=[],
            directives=[directive],
        )
        with pytest.raises(ConclaveConfigError, match="Arbiter"):
            c.assemble()


# ---------------------------------------------------------------------------
# Sequential execution tests
# ---------------------------------------------------------------------------


class TestSequentialExecution:
    """Tests for Protocol.sequential execution."""

    def test_sequential_returns_conclave_result(
        self, mock_llm: MagicMock
    ) -> None:
        """assemble() should return a ConclaveResult."""
        mock_llm.complete.return_value = "Done."
        arbiter = make_mock_arbiter("Analyst", mock_llm)
        directive = make_directive("Analyse data", arbiter)
        c = Conclave(
            arbiters=[arbiter],
            directives=[directive],
            protocol=Protocol.sequential,
        )
        result = c.assemble()
        assert isinstance(result, ConclaveResult)

    def test_sequential_final_output_is_last_directive(
        self, mock_llm: MagicMock
    ) -> None:
        """final_output should be the output of the last directive."""
        mock_llm.complete.return_value = "Last output."
        arbiter = make_mock_arbiter("R", mock_llm)
        d1 = make_directive("D1", arbiter)
        d2 = make_directive("D2", arbiter)
        c = Conclave(
            arbiters=[arbiter],
            directives=[d1, d2],
            protocol=Protocol.sequential,
        )
        result = c.assemble()
        assert result.final_output == "Last output."

    def test_sequential_result_count_matches_directives(
        self, mock_llm: MagicMock
    ) -> None:
        """directive_results count should match directives count."""
        mock_llm.complete.return_value = "ok"
        arbiter = make_mock_arbiter("R", mock_llm)
        d1 = make_directive("D1", arbiter)
        d2 = make_directive("D2", arbiter)
        d3 = make_directive("D3", arbiter)
        c = Conclave(
            arbiters=[arbiter],
            directives=[d1, d2, d3],
            protocol=Protocol.sequential,
        )
        result = c.assemble()
        assert len(result.directive_results) == 3

    def test_sequential_directives_marked_complete(
        self, mock_llm: MagicMock
    ) -> None:
        """Directives should have mark_complete called after execution."""
        mock_llm.complete.return_value = "done"
        arbiter = make_mock_arbiter("R", mock_llm)
        directive = make_directive("D", arbiter)
        c = Conclave(
            arbiters=[arbiter],
            directives=[directive],
            protocol=Protocol.sequential,
        )
        c.assemble()
        assert directive.result is not None

    def test_sequential_context_passed_to_later_directives(
        self, mock_llm: MagicMock
    ) -> None:
        """Later directives should receive context from earlier ones."""
        responses = ["First output", "Second output"]
        mock_llm.complete.side_effect = responses
        arbiter = make_mock_arbiter("R", mock_llm)
        d1 = make_directive("D1", arbiter)
        d2 = make_directive("D2", arbiter)
        c = Conclave(
            arbiters=[arbiter],
            directives=[d1, d2],
        )
        c.assemble()
        # The second complete call should contain context from first
        second_call_messages = mock_llm.complete.call_args_list[1]
        # messages is the first positional arg
        messages = second_call_messages[1]["messages"]
        context_found = any("First output" in str(m) for m in messages)
        assert context_found

    def test_round_robin_arbiter_assignment(self, mock_llm: MagicMock) -> None:
        """Without explicit arbiter, conclave assigns via round-robin."""
        mock_llm.complete.return_value = "done"
        a1 = make_mock_arbiter("R1", mock_llm)
        a2 = make_mock_arbiter("R2", mock_llm)
        # Directives without explicit arbiter
        d1 = Directive(description="D1", expected_output="E1")
        d2 = Directive(description="D2", expected_output="E2")
        c = Conclave(
            arbiters=[a1, a2],
            directives=[d1, d2],
        )
        result = c.assemble()
        assert len(result.directive_results) == 2

    def test_retry_on_failure_raises_after_max(
        self, mock_llm: MagicMock
    ) -> None:
        """Conclave should raise after exhausting all retries."""
        mock_llm.complete.side_effect = RuntimeError("LLM error")
        arbiter = make_mock_arbiter("R", mock_llm)
        directive = make_directive("D", arbiter)
        c = Conclave(
            arbiters=[arbiter],
            directives=[directive],
            max_retries=2,
        )
        with pytest.raises(RuntimeError, match="failed after"):
            c.assemble()

    def test_output_log_file_written(
        self, mock_llm: MagicMock, tmp_path
    ) -> None:
        """assemble() should write output to output_log_file."""
        mock_llm.complete.return_value = "logged output"
        arbiter = make_mock_arbiter("R", mock_llm)
        directive = make_directive("D", arbiter)
        log_path = str(tmp_path / "log.txt")
        c = Conclave(
            arbiters=[arbiter],
            directives=[directive],
            output_log_file=log_path,
        )
        c.assemble()
        assert (tmp_path / "log.txt").read_text() == "logged output"
