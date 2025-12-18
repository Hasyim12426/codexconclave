"""Unit tests for the Arbiter class."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from codexconclave.arbiter.core import Arbiter, ArbiterResult
from codexconclave.directive import Directive

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_arbiter(llm: MagicMock) -> Arbiter:
    """Create a test Arbiter with a mocked LLM.

    Args:
        llm: Mock LLM provider.

    Returns:
        Arbiter: Configured test Arbiter.
    """
    return Arbiter(
        role="Test Arbiter",
        objective="Complete test tasks accurately.",
        persona="A precise test agent.",
        llm=llm,
        verbose=False,
    )


def make_directive(description: str = "Do something") -> Directive:
    """Create a simple test Directive.

    Args:
        description: The directive description.

    Returns:
        Directive: A configured test Directive.
    """
    return Directive(
        description=description,
        expected_output="A correct result.",
    )


# ---------------------------------------------------------------------------
# ArbiterResult tests
# ---------------------------------------------------------------------------


class TestArbiterResult:
    """Tests for ArbiterResult model."""

    def test_basic_construction(self) -> None:
        """ArbiterResult should be constructable with minimal fields."""
        result = ArbiterResult(
            output="hello",
            directive_description="do x",
            arbiter_role="Tester",
            raw_output="hello",
        )
        assert result.output == "hello"
        assert result.arbiter_role == "Tester"
        assert result.iterations == 0
        assert result.execution_time_ms == 0.0

    def test_structured_output_defaults_none(self) -> None:
        """structured_output should default to None."""
        result = ArbiterResult(
            output="x",
            directive_description="d",
            arbiter_role="r",
            raw_output="x",
        )
        assert result.structured_output is None


# ---------------------------------------------------------------------------
# Arbiter initialisation tests
# ---------------------------------------------------------------------------


class TestArbiterInit:
    """Tests for Arbiter field defaults and initialisation."""

    def test_role_stored(self, mock_llm: MagicMock) -> None:
        """role field should be stored on the Arbiter."""
        arbiter = Arbiter(
            role="Analyst",
            objective="Analyse things.",
            llm=mock_llm,
        )
        assert arbiter.role == "Analyst"

    def test_objective_stored(self, mock_llm: MagicMock) -> None:
        """objective field should be stored."""
        arbiter = Arbiter(
            role="R",
            objective="My objective",
            llm=mock_llm,
        )
        assert arbiter.objective == "My objective"

    def test_default_persona_empty(self, mock_llm: MagicMock) -> None:
        """Default persona should be empty string."""
        arbiter = Arbiter(role="R", objective="O", llm=mock_llm)
        assert arbiter.persona == ""

    def test_default_max_iterations(self, mock_llm: MagicMock) -> None:
        """Default max_iterations should be 20."""
        arbiter = Arbiter(role="R", objective="O", llm=mock_llm)
        assert arbiter.max_iterations == 20

    def test_instruments_default_empty(self, mock_llm: MagicMock) -> None:
        """instruments should default to an empty list."""
        arbiter = Arbiter(role="R", objective="O", llm=mock_llm)
        assert arbiter.instruments == []

    def test_allow_delegation_default_false(self, mock_llm: MagicMock) -> None:
        """allow_delegation should default to False."""
        arbiter = Arbiter(role="R", objective="O", llm=mock_llm)
        assert arbiter.allow_delegation is False


# ---------------------------------------------------------------------------
# Arbiter.perform() tests
# ---------------------------------------------------------------------------


class TestArbiterPerform:
    """Tests for the perform() execution method."""

    def test_perform_returns_arbiter_result(self, mock_llm: MagicMock) -> None:
        """perform() should return an ArbiterResult."""
        mock_llm.complete.return_value = "Final answer"
        arbiter = make_arbiter(mock_llm)
        directive = make_directive()
        result = arbiter.perform(directive)
        assert isinstance(result, ArbiterResult)

    def test_perform_output_matches_llm_response(
        self, mock_llm: MagicMock
    ) -> None:
        """output should contain the LLM's response."""
        mock_llm.complete.return_value = "The answer is 42."
        arbiter = make_arbiter(mock_llm)
        directive = make_directive()
        result = arbiter.perform(directive)
        assert "42" in result.output

    def test_perform_stores_arbiter_role(self, mock_llm: MagicMock) -> None:
        """ArbiterResult.arbiter_role should match arbiter.role."""
        mock_llm.complete.return_value = "Done."
        arbiter = make_arbiter(mock_llm)
        directive = make_directive()
        result = arbiter.perform(directive)
        assert result.arbiter_role == "Test Arbiter"

    def test_perform_with_context(self, mock_llm: MagicMock) -> None:
        """perform() should accept and use context string."""
        mock_llm.complete.return_value = "Based on context: done."
        arbiter = make_arbiter(mock_llm)
        directive = make_directive()
        result = arbiter.perform(directive, context="prior output")
        assert isinstance(result, ArbiterResult)

    def test_perform_calls_llm_complete(self, mock_llm: MagicMock) -> None:
        """perform() should call llm.complete at least once."""
        mock_llm.complete.return_value = "response"
        arbiter = make_arbiter(mock_llm)
        directive = make_directive()
        arbiter.perform(directive)
        mock_llm.complete.assert_called()

    def test_perform_time_limit_raises(self, mock_llm: MagicMock) -> None:
        """Arbiter should raise TimeoutError when time limit is exceeded."""
        call_count = 0

        def slow_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            import time

            time.sleep(0.2)
            # Return a JSON that triggers instrument loop
            return '{"instrument": "nonexistent", "arguments": {}}'

        mock_llm.complete.side_effect = slow_complete

        arbiter = Arbiter(
            role="R",
            objective="O",
            llm=mock_llm,
            max_execution_time=0.01,
        )
        directive = make_directive()
        with pytest.raises(TimeoutError):
            arbiter.perform(directive)

    def test_perform_iteration_limit(self, mock_llm: MagicMock) -> None:
        """Arbiter should stop after max_iterations."""
        # Always return an instrument call that doesn't exist
        mock_llm.complete.return_value = (
            '{"instrument": "fake", "arguments": {}}'
        )
        arbiter = Arbiter(
            role="R",
            objective="O",
            llm=mock_llm,
            max_iterations=3,
        )
        directive = make_directive()
        result = arbiter.perform(directive)
        # Should not loop forever — should give back whatever the LLM said
        assert isinstance(result, ArbiterResult)

    def test_perform_with_output_format(self, mock_llm: MagicMock) -> None:
        """perform() with output_format should parse structured output."""
        from pydantic import BaseModel as PydanticModel

        class Answer(PydanticModel):
            value: str

        mock_llm.complete.return_value = '{"value": "42"}'
        arbiter = make_arbiter(mock_llm)
        directive = Directive(
            description="What is the answer?",
            expected_output="A JSON answer object.",
            output_format=Answer,
        )
        result = arbiter.perform(directive)
        assert isinstance(result.structured_output, Answer)
        assert result.structured_output.value == "42"

    def test_perform_with_guardrail_passes(self, mock_llm: MagicMock) -> None:
        """Guardrail that passes should return cleaned output."""
        mock_llm.complete.return_value = "  raw answer  "
        arbiter = make_arbiter(mock_llm)
        directive = Directive(
            description="Answer question",
            expected_output="Clean answer",
            guardrail=lambda x: (True, x.strip()),
        )
        result = arbiter.perform(directive)
        assert result.output == "raw answer"

    def test_perform_writes_output_file(
        self, mock_llm: MagicMock, tmp_path
    ) -> None:
        """perform() should write output to output_file when specified."""
        mock_llm.complete.return_value = "file content"
        arbiter = make_arbiter(mock_llm)
        out_file = str(tmp_path / "output.txt")
        directive = Directive(
            description="Generate content",
            expected_output="Some content",
            output_file=out_file,
        )
        arbiter.perform(directive)
        assert (tmp_path / "output.txt").read_text() == "file content"
