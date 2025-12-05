"""Unit tests for the signals subsystem."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from codexconclave.signals.bus import SignalBus
from codexconclave.signals.listener import BaseSignalListener
from codexconclave.signals.types import (
    ArbiterCompletedSignal,
    ArbiterErrorSignal,
    ArbiterStartedSignal,
    ConclaveStartedSignal,
    DirectiveStartedSignal,
    InstrumentUsedSignal,
    LLMCallSignal,
    Signal,
)

# ---------------------------------------------------------------------------
# Helper listener implementations
# ---------------------------------------------------------------------------


class AllListener(BaseSignalListener):
    """Listener that accepts all signals."""

    def __init__(self) -> None:
        self.received: list[Signal] = []

    def handle(self, signal: Signal) -> None:
        self.received.append(signal)


class FilteredListener(BaseSignalListener):
    """Listener that only accepts ArbiterStartedSignal."""

    signal_types = (ArbiterStartedSignal,)

    def __init__(self) -> None:
        self.received: list[Signal] = []

    def handle(self, signal: Signal) -> None:
        self.received.append(signal)


# ---------------------------------------------------------------------------
# Signal type tests
# ---------------------------------------------------------------------------


class TestSignalTypes:
    """Tests for individual signal model construction."""

    def test_base_signal_auto_id(self) -> None:
        """Signal should auto-generate a unique ID."""
        s1 = Signal()
        s2 = Signal()
        assert s1.id != s2.id

    def test_base_signal_timestamp(self) -> None:
        """Signal should have a UTC timestamp."""
        s = Signal()
        assert s.timestamp is not None

    def test_arbiter_started_signal(self) -> None:
        """ArbiterStartedSignal should carry role and description."""
        sig = ArbiterStartedSignal(
            arbiter_role="Researcher",
            directive_description="Do research",
        )
        assert sig.arbiter_role == "Researcher"
        assert sig.directive_description == "Do research"

    def test_arbiter_completed_signal(self) -> None:
        """ArbiterCompletedSignal should carry role and output."""
        sig = ArbiterCompletedSignal(
            arbiter_role="Writer",
            output="The report is done.",
        )
        assert sig.arbiter_role == "Writer"
        assert sig.output == "The report is done."

    def test_arbiter_error_signal(self) -> None:
        """ArbiterErrorSignal should carry role and error string."""
        sig = ArbiterErrorSignal(
            arbiter_role="Tester",
            error="Something went wrong",
        )
        assert sig.error == "Something went wrong"

    def test_conclave_started_signal(self) -> None:
        """ConclaveStartedSignal should carry counts."""
        sig = ConclaveStartedSignal(directive_count=3, arbiter_count=2)
        assert sig.directive_count == 3
        assert sig.arbiter_count == 2

    def test_instrument_used_signal_cached_default(self) -> None:
        """InstrumentUsedSignal.cached should default to False."""
        sig = InstrumentUsedSignal(
            instrument_name="search",
            input_summary="query",
            output_summary="result",
        )
        assert sig.cached is False

    def test_llm_call_signal(self) -> None:
        """LLMCallSignal should carry model and token counts."""
        sig = LLMCallSignal(
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
        )
        assert sig.model == "gpt-4o"
        assert sig.prompt_tokens == 100
        assert sig.completion_tokens == 50

    def test_signal_immutability(self) -> None:
        """Signals should be immutable (frozen models)."""
        sig = Signal()
        with pytest.raises((TypeError, ValueError)):
            sig.source = "modified"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SignalBus tests
# ---------------------------------------------------------------------------


class TestSignalBus:
    """Tests for the SignalBus singleton and dispatch logic."""

    def setup_method(self) -> None:
        """Reset the singleton before each test."""
        SignalBus.reset()

    def test_singleton(self) -> None:
        """SignalBus.instance() should return the same object."""
        bus1 = SignalBus.instance()
        bus2 = SignalBus.instance()
        assert bus1 is bus2

    def test_register_listener(self) -> None:
        """Registering a listener should increment listener count."""
        bus = SignalBus.instance()
        listener = AllListener()
        bus.register(listener)
        assert bus.listener_count() == 1

    def test_register_duplicate_is_noop(self) -> None:
        """Registering the same listener twice should not duplicate it."""
        bus = SignalBus.instance()
        listener = AllListener()
        bus.register(listener)
        bus.register(listener)
        assert bus.listener_count() == 1

    def test_unregister_listener(self) -> None:
        """Unregistering a listener should remove it."""
        bus = SignalBus.instance()
        listener = AllListener()
        bus.register(listener)
        bus.unregister(listener)
        assert bus.listener_count() == 0

    def test_unregister_unknown_is_noop(self) -> None:
        """Unregistering a listener that was never registered is safe."""
        bus = SignalBus.instance()
        listener = AllListener()
        bus.unregister(listener)  # should not raise

    def test_emit_delivers_to_listener(self) -> None:
        """Emitting a signal should call handle on accepting listeners."""
        bus = SignalBus.instance()
        listener = AllListener()
        bus.register(listener)

        sig = ConclaveStartedSignal(directive_count=1, arbiter_count=1)
        bus.emit(sig)

        assert len(listener.received) == 1
        assert listener.received[0] is sig

    def test_emit_filtered_listener(self) -> None:
        """Filtered listener should only receive its accepted types."""
        bus = SignalBus.instance()
        filtered = FilteredListener()
        bus.register(filtered)

        # This should NOT be received
        bus.emit(ConclaveStartedSignal(directive_count=1, arbiter_count=1))
        # This SHOULD be received
        bus.emit(
            ArbiterStartedSignal(
                arbiter_role="R",
                directive_description="D",
            )
        )

        assert len(filtered.received) == 1
        assert isinstance(filtered.received[0], ArbiterStartedSignal)

    def test_emit_exception_in_listener_does_not_propagate(self) -> None:
        """An exception in a listener should not stop other listeners."""
        bus = SignalBus.instance()

        bad_listener = MagicMock(spec=BaseSignalListener)
        bad_listener.accepts.return_value = True
        bad_listener.handle.side_effect = RuntimeError("boom")

        good_listener = AllListener()

        bus.register(bad_listener)
        bus.register(good_listener)

        sig = Signal()
        bus.emit(sig)  # should not raise

        assert len(good_listener.received) == 1


# ---------------------------------------------------------------------------
# BaseSignalListener tests
# ---------------------------------------------------------------------------


class TestBaseSignalListener:
    """Tests for the listener filter logic."""

    def test_empty_signal_types_accepts_all(self) -> None:
        """A listener with no signal_types filter accepts everything."""
        listener = AllListener()
        assert listener.accepts(Signal()) is True
        assert (
            listener.accepts(
                ConclaveStartedSignal(directive_count=1, arbiter_count=1)
            )
            is True
        )

    def test_typed_listener_filters_correctly(self) -> None:
        """A typed listener should accept only its declared types."""
        listener = FilteredListener()
        arbiter_sig = ArbiterStartedSignal(
            arbiter_role="R", directive_description="D"
        )
        other_sig = DirectiveStartedSignal(
            directive_description="D", arbiter_role="R"
        )

        assert listener.accepts(arbiter_sig) is True
        assert listener.accepts(other_sig) is False
