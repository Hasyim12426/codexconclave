"""Unit tests for the Directive class."""

from __future__ import annotations

from pydantic import BaseModel

from codexconclave.directive import Directive, DirectiveResult

# ---------------------------------------------------------------------------
# DirectiveResult tests
# ---------------------------------------------------------------------------


class TestDirectiveResult:
    """Tests for the DirectiveResult model."""

    def test_construction(self) -> None:
        """DirectiveResult should be constructable with required fields."""
        result = DirectiveResult(
            description="Do X",
            expected_output="Result of X",
            raw_output="raw",
            output="clean",
            agent_role="Analyst",
        )
        assert result.description == "Do X"
        assert result.output == "clean"
        assert result.agent_role == "Analyst"

    def test_structured_output_defaults_none(self) -> None:
        """structured_output should default to None."""
        result = DirectiveResult(
            description="D",
            expected_output="E",
            raw_output="r",
            output="o",
            agent_role="A",
        )
        assert result.structured_output is None

    def test_output_file_defaults_none(self) -> None:
        """output_file should default to None."""
        result = DirectiveResult(
            description="D",
            expected_output="E",
            raw_output="r",
            output="o",
            agent_role="A",
        )
        assert result.output_file is None


# ---------------------------------------------------------------------------
# Directive construction tests
# ---------------------------------------------------------------------------


class TestDirectiveConstruction:
    """Tests for Directive construction and defaults."""

    def test_basic_construction(self) -> None:
        """Directive should be constructable with description + expected."""
        d = Directive(
            description="Research AI",
            expected_output="AI summary",
        )
        assert d.description == "Research AI"
        assert d.expected_output == "AI summary"

    def test_arbiter_defaults_none(self) -> None:
        """arbiter should default to None."""
        d = Directive(description="D", expected_output="E")
        assert d.arbiter is None

    def test_context_defaults_empty_list(self) -> None:
        """context should default to an empty list."""
        d = Directive(description="D", expected_output="E")
        assert d.context == []

    def test_instruments_default_empty(self) -> None:
        """instruments should default to an empty list."""
        d = Directive(description="D", expected_output="E")
        assert d.instruments == []

    def test_async_execution_default_false(self) -> None:
        """async_execution should default to False."""
        d = Directive(description="D", expected_output="E")
        assert d.async_execution is False

    def test_output_format_defaults_none(self) -> None:
        """output_format should default to None."""
        d = Directive(description="D", expected_output="E")
        assert d.output_format is None

    def test_output_file_defaults_none(self) -> None:
        """output_file should default to None."""
        d = Directive(description="D", expected_output="E")
        assert d.output_file is None

    def test_callback_defaults_none(self) -> None:
        """callback should default to None."""
        d = Directive(description="D", expected_output="E")
        assert d.callback is None

    def test_guardrail_defaults_none(self) -> None:
        """guardrail should default to None."""
        d = Directive(description="D", expected_output="E")
        assert d.guardrail is None


# ---------------------------------------------------------------------------
# Directive.mark_complete() tests
# ---------------------------------------------------------------------------


class TestDirectiveMarkComplete:
    """Tests for the mark_complete() lifecycle hook."""

    def _make_result(self) -> DirectiveResult:
        return DirectiveResult(
            description="D",
            expected_output="E",
            raw_output="raw",
            output="clean",
            agent_role="Analyst",
        )

    def test_result_stored(self) -> None:
        """mark_complete should store the result."""
        d = Directive(description="D", expected_output="E")
        result = self._make_result()
        d.mark_complete(result)
        assert d.result is result

    def test_callback_invoked(self) -> None:
        """mark_complete should invoke the callback with the result."""
        received: list[DirectiveResult] = []
        d = Directive(
            description="D",
            expected_output="E",
            callback=received.append,
        )
        result = self._make_result()
        d.mark_complete(result)
        assert len(received) == 1
        assert received[0] is result

    def test_callback_exception_does_not_propagate(self) -> None:
        """A callback that raises should not propagate the exception."""

        def bad_callback(r: DirectiveResult) -> None:
            raise RuntimeError("callback error")

        d = Directive(
            description="D",
            expected_output="E",
            callback=bad_callback,
        )
        result = self._make_result()
        d.mark_complete(result)  # should not raise

    def test_result_property_before_complete(self) -> None:
        """result property should be None before mark_complete is called."""
        d = Directive(description="D", expected_output="E")
        assert d.result is None


# ---------------------------------------------------------------------------
# Directive context linking tests
# ---------------------------------------------------------------------------


class TestDirectiveContext:
    """Tests for context-linked directives."""

    def test_context_links_directives(self) -> None:
        """Linked context directives should be accessible."""
        d1 = Directive(description="First", expected_output="E1")
        d2 = Directive(
            description="Second",
            expected_output="E2",
            context=[d1],
        )
        assert d1 in d2.context

    def test_multiple_context_links(self) -> None:
        """Multiple context links should all be preserved."""
        d1 = Directive(description="D1", expected_output="E1")
        d2 = Directive(description="D2", expected_output="E2")
        d3 = Directive(
            description="D3",
            expected_output="E3",
            context=[d1, d2],
        )
        assert len(d3.context) == 2

    def test_output_format_pydantic_model(self) -> None:
        """output_format should accept a Pydantic model class."""

        class MyOutput(BaseModel):
            answer: str

        d = Directive(
            description="D",
            expected_output="E",
            output_format=MyOutput,
        )
        assert d.output_format is MyOutput
