"""Integration tests for full Conclave execution flow.

These tests wire together real Arbiter, Directive, and Conclave
instances but mock the LLM layer so no network calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from codexconclave.arbiter.core import Arbiter
from codexconclave.conclave import Conclave, ConclaveResult
from codexconclave.directive import Directive, DirectiveResult
from codexconclave.protocol import Protocol
from codexconclave.signals.bus import SignalBus
from codexconclave.signals.listener import BaseSignalListener
from codexconclave.signals.types import (
    ConclaveCompletedSignal,
    ConclaveStartedSignal,
    DirectiveCompletedSignal,
    DirectiveStartedSignal,
    Signal,
)

# ---------------------------------------------------------------------------
# Signal capture helper
# ---------------------------------------------------------------------------


class CapturingListener(BaseSignalListener):
    """Listener that records all signals for assertion."""

    def __init__(self) -> None:
        self.signals: list[Signal] = []

    def handle(self, signal: Signal) -> None:
        self.signals.append(signal)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_bus():
    """Reset the SignalBus singleton before each integration test."""
    SignalBus.reset()
    yield
    SignalBus.reset()


@pytest.fixture
def mock_llm_provider():
    """Return a mock LLMProvider with configurable response."""
    llm = MagicMock()
    llm.model = "gpt-4o"
    llm.context_window = 128_000
    llm.complete.return_value = "Integration test response."
    return llm


# ---------------------------------------------------------------------------
# Full sequential flow
# ---------------------------------------------------------------------------


class TestFullSequentialFlow:
    """End-to-end integration tests for sequential Conclave execution."""

    def test_single_directive_full_flow(
        self, mock_llm_provider: MagicMock
    ) -> None:
        """A single-directive Conclave should complete successfully."""
        arbiter = Arbiter(
            role="Analyst",
            objective="Provide analysis.",
            llm=mock_llm_provider,
        )
        directive = Directive(
            description="Analyse the current AI landscape.",
            expected_output="A concise analysis.",
            arbiter=arbiter,
        )
        conclave = Conclave(
            arbiters=[arbiter],
            directives=[directive],
            protocol=Protocol.sequential,
        )
        result = conclave.assemble()

        assert isinstance(result, ConclaveResult)
        assert result.final_output == "Integration test response."
        assert len(result.directive_results) == 1

    def test_multi_directive_context_propagation(
        self, mock_llm_provider: MagicMock
    ) -> None:
        """Context from directive 1 should reach directive 2's LLM call."""
        responses = [
            "First: AI emerged in 1956.",
            "Second: building on prior context.",
        ]
        mock_llm_provider.complete.side_effect = responses

        researcher = Arbiter(
            role="Researcher",
            objective="Research AI history.",
            llm=mock_llm_provider,
        )
        writer = Arbiter(
            role="Writer",
            objective="Write a report.",
            llm=mock_llm_provider,
        )
        d1 = Directive(
            description="Research AI origins.",
            expected_output="Historical facts.",
            arbiter=researcher,
        )
        d2 = Directive(
            description="Write a report based on research.",
            expected_output="A complete report.",
            arbiter=writer,
        )
        conclave = Conclave(
            arbiters=[researcher, writer],
            directives=[d1, d2],
            protocol=Protocol.sequential,
        )
        result = conclave.assemble()

        assert len(result.directive_results) == 2
        # Second call should have context containing first output
        second_call = mock_llm_provider.complete.call_args_list[1]
        messages = second_call[1]["messages"]
        full_text = " ".join(str(m) for m in messages)
        assert "First: AI emerged" in full_text

    def test_directive_results_have_correct_agent_roles(
        self, mock_llm_provider: MagicMock
    ) -> None:
        """Each DirectiveResult should record the correct agent_role."""
        mock_llm_provider.complete.return_value = "done"
        r1 = Arbiter(role="Role1", objective="O1", llm=mock_llm_provider)
        r2 = Arbiter(role="Role2", objective="O2", llm=mock_llm_provider)
        d1 = Directive(description="D1", expected_output="E1", arbiter=r1)
        d2 = Directive(description="D2", expected_output="E2", arbiter=r2)
        conclave = Conclave(
            arbiters=[r1, r2],
            directives=[d1, d2],
        )
        result = conclave.assemble()

        assert result.directive_results[0].agent_role == "Role1"
        assert result.directive_results[1].agent_role == "Role2"

    def test_conclave_result_str(self, mock_llm_provider: MagicMock) -> None:
        """str(ConclaveResult) should equal final_output."""
        mock_llm_provider.complete.return_value = "Final answer."
        arbiter = Arbiter(role="R", objective="O", llm=mock_llm_provider)
        directive = Directive(
            description="D", expected_output="E", arbiter=arbiter
        )
        conclave = Conclave(
            arbiters=[arbiter],
            directives=[directive],
        )
        result = conclave.assemble()
        assert str(result) == "Final answer."


# ---------------------------------------------------------------------------
# Signal emission verification
# ---------------------------------------------------------------------------


class TestSignalEmission:
    """Verify that correct signals are emitted during Conclave execution."""

    def test_conclave_started_signal_emitted(
        self, mock_llm_provider: MagicMock
    ) -> None:
        """ConclaveStartedSignal should be emitted at the start."""
        listener = CapturingListener()
        SignalBus.instance().register(listener)

        mock_llm_provider.complete.return_value = "ok"
        arbiter = Arbiter(role="R", objective="O", llm=mock_llm_provider)
        directive = Directive(
            description="D", expected_output="E", arbiter=arbiter
        )
        Conclave(arbiters=[arbiter], directives=[directive]).assemble()

        started = [
            s for s in listener.signals if isinstance(s, ConclaveStartedSignal)
        ]
        assert len(started) == 1
        assert started[0].directive_count == 1
        assert started[0].arbiter_count == 1

    def test_conclave_completed_signal_emitted(
        self, mock_llm_provider: MagicMock
    ) -> None:
        """ConclaveCompletedSignal should be emitted on completion."""
        listener = CapturingListener()
        SignalBus.instance().register(listener)

        mock_llm_provider.complete.return_value = "final"
        arbiter = Arbiter(role="R", objective="O", llm=mock_llm_provider)
        directive = Directive(
            description="D", expected_output="E", arbiter=arbiter
        )
        Conclave(arbiters=[arbiter], directives=[directive]).assemble()

        completed = [
            s
            for s in listener.signals
            if isinstance(s, ConclaveCompletedSignal)
        ]
        assert len(completed) == 1

    def test_directive_signals_emitted(
        self, mock_llm_provider: MagicMock
    ) -> None:
        """DirectiveStarted and DirectiveCompleted should be emitted."""
        listener = CapturingListener()
        SignalBus.instance().register(listener)

        mock_llm_provider.complete.return_value = "ok"
        arbiter = Arbiter(role="R", objective="O", llm=mock_llm_provider)
        directive = Directive(
            description="D", expected_output="E", arbiter=arbiter
        )
        Conclave(arbiters=[arbiter], directives=[directive]).assemble()

        started = [
            s
            for s in listener.signals
            if isinstance(s, DirectiveStartedSignal)
        ]
        completed = [
            s
            for s in listener.signals
            if isinstance(s, DirectiveCompletedSignal)
        ]
        assert len(started) == 1
        assert len(completed) == 1


# ---------------------------------------------------------------------------
# Callback and guardrail integration
# ---------------------------------------------------------------------------


class TestCallbacksAndGuardrails:
    """Integration tests for directive callbacks and guardrails."""

    def test_directive_callback_invoked(
        self, mock_llm_provider: MagicMock
    ) -> None:
        """The directive callback should be called with the result."""
        received: list[DirectiveResult] = []
        mock_llm_provider.complete.return_value = "callback output"

        arbiter = Arbiter(role="R", objective="O", llm=mock_llm_provider)
        directive = Directive(
            description="D",
            expected_output="E",
            arbiter=arbiter,
            callback=received.append,
        )
        Conclave(arbiters=[arbiter], directives=[directive]).assemble()

        assert len(received) == 1
        assert received[0].output == "callback output"

    def test_guardrail_cleans_output(
        self, mock_llm_provider: MagicMock
    ) -> None:
        """A passing guardrail should transform the output."""
        mock_llm_provider.complete.return_value = "  raw output  "
        arbiter = Arbiter(role="R", objective="O", llm=mock_llm_provider)
        directive = Directive(
            description="D",
            expected_output="E",
            arbiter=arbiter,
            guardrail=lambda x: (True, x.strip()),
        )
        result = Conclave(
            arbiters=[arbiter], directives=[directive]
        ).assemble()
        assert result.final_output == "raw output"


# ---------------------------------------------------------------------------
# Delegation integration
# ---------------------------------------------------------------------------


class TestDelegation:
    """Integration test for Arbiter delegation."""

    def test_delegation_to_peer(self, mock_llm_provider: MagicMock) -> None:
        """An Arbiter with allow_delegation=True should be able to
        delegate to a peer and the Conclave should complete."""
        # Sequence: first call returns a delegation request,
        # second call (by the delegate) returns a real answer,
        # third call (back to original) gives final answer.
        call_count = 0

        def smart_complete(messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return '{"delegate_to": "Helper", "task": "provide data"}'
            return "delegation complete"

        mock_llm_provider.complete.side_effect = smart_complete

        helper_llm = MagicMock()
        helper_llm.model = "gpt-4o"
        helper_llm.complete.return_value = "helper data"

        main_arbiter = Arbiter(
            role="Coordinator",
            objective="Coordinate work.",
            llm=mock_llm_provider,
            allow_delegation=True,
        )
        helper_arbiter = Arbiter(
            role="Helper",
            objective="Provide data.",
            llm=helper_llm,
        )
        directive = Directive(
            description="Coordinate and gather data.",
            expected_output="Final report.",
            arbiter=main_arbiter,
        )
        conclave = Conclave(
            arbiters=[main_arbiter, helper_arbiter],
            directives=[directive],
        )
        result = conclave.assemble()
        assert isinstance(result, ConclaveResult)
