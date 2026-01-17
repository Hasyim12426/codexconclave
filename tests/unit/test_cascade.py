"""Unit tests for the Cascade pipeline system."""

from __future__ import annotations

import pytest

from codexconclave.cascade.decorators import (
    INITIATE_TAG,
    OBSERVE_TAG,
    OBSERVE_TARGETS,
    ROUTE_TAG,
    and_,
    initiate,
    observe,
    or_,
    route,
)
from codexconclave.cascade.pipeline import (
    Cascade,
    CascadeExecutionError,
    CascadeResult,
)
from codexconclave.cascade.state import (
    CascadeState,
    UnstructuredCascadeState,
)

# ---------------------------------------------------------------------------
# Decorator tests
# ---------------------------------------------------------------------------


class TestInitiateDecorator:
    """Tests for the @initiate decorator."""

    def test_sets_initiate_tag(self) -> None:
        """@initiate should set INITIATE_TAG on the function."""

        @initiate
        def my_method():
            pass

        assert getattr(my_method, INITIATE_TAG) is True

    def test_preserves_function_name(self) -> None:
        """@initiate should not change the function name."""

        @initiate
        def start():
            pass

        assert start.__name__ == "start"


class TestObserveDecorator:
    """Tests for the @observe decorator."""

    def test_sets_observe_tag(self) -> None:
        """@observe should set OBSERVE_TAG on the function."""

        def start():
            pass

        @observe(start)
        def after_start():
            pass

        assert getattr(after_start, OBSERVE_TAG) is True

    def test_stores_target_name(self) -> None:
        """@observe should store the target method name."""

        def start():
            pass

        @observe(start)
        def after():
            pass

        targets = getattr(after, OBSERVE_TARGETS)
        assert "start" in targets

    def test_stores_string_target(self) -> None:
        """@observe should accept string target names."""

        @observe("my_method")
        def handler():
            pass

        targets = getattr(handler, OBSERVE_TARGETS)
        assert "my_method" in targets

    def test_multiple_targets(self) -> None:
        """@observe should store all provided targets."""

        def a():
            pass

        def b():
            pass

        @observe(a, b)
        def after():
            pass

        targets = getattr(after, OBSERVE_TARGETS)
        assert "a" in targets
        assert "b" in targets


class TestRouteDecorator:
    """Tests for the @route decorator."""

    def test_sets_route_tag(self) -> None:
        """@route should set ROUTE_TAG on the function."""

        @route
        def my_router():
            pass

        assert getattr(my_router, ROUTE_TAG) is True


class TestAndOrHelpers:
    """Tests for and_() and or_() condition helpers."""

    def test_and_returns_tuple(self) -> None:
        """and_() should return ('AND', conditions) tuple."""
        result = and_("a", "b")
        assert result[0] == "AND"

    def test_or_returns_tuple(self) -> None:
        """or_() should return ('OR', conditions) tuple."""
        result = or_("a", "b")
        assert result[0] == "OR"

    def test_and_conditions_preserved(self) -> None:
        """and_() should preserve all conditions."""
        result = and_("x", "y", "z")
        assert len(result[1]) == 3

    def test_or_conditions_preserved(self) -> None:
        """or_() should preserve all conditions."""
        result = or_("p", "q")
        assert len(result[1]) == 2


# ---------------------------------------------------------------------------
# CascadeState tests
# ---------------------------------------------------------------------------


class TestCascadeState:
    """Tests for the state models."""

    def test_run_id_auto_generated(self) -> None:
        """CascadeState should auto-generate a unique run_id."""
        s1 = CascadeState()
        s2 = CascadeState()
        assert s1.run_id != s2.run_id

    def test_run_id_is_string(self) -> None:
        """run_id should be a string."""
        s = CascadeState()
        assert isinstance(s.run_id, str)


class TestUnstructuredCascadeState:
    """Tests for UnstructuredCascadeState dynamic attributes."""

    def test_set_and_get_dynamic_attr(self) -> None:
        """Should support setting and getting arbitrary attributes."""
        state = UnstructuredCascadeState()
        state.answer = "42"
        assert state.answer == "42"

    def test_missing_attr_returns_none(self) -> None:
        """Accessing an unset attribute should return None."""
        state = UnstructuredCascadeState()
        assert state.nonexistent is None

    def test_model_fields_still_work(self) -> None:
        """Pydantic model fields should not be intercepted."""
        state = UnstructuredCascadeState()
        assert state.run_id is not None

    def test_data_dict_populated(self) -> None:
        """Setting a dynamic attribute should update the data dict."""
        state = UnstructuredCascadeState()
        state.x = 10
        assert state.data["x"] == 10


# ---------------------------------------------------------------------------
# Cascade pipeline tests
# ---------------------------------------------------------------------------


class SimplePipeline(Cascade):
    """A minimal two-step pipeline for testing."""

    state: CascadeState = CascadeState()

    @initiate
    def begin(self) -> str:
        """Entry point."""
        return "hello"

    @observe(begin)
    def process(self, value: str) -> str:
        """Observer receiving begin's output."""
        return value.upper()


class RoutingPipeline(Cascade):
    """Pipeline that uses @route to branch."""

    state: UnstructuredCascadeState = UnstructuredCascadeState()

    @initiate
    def start(self) -> str:
        return "route_me"

    @route
    @observe(start)
    def decide(self, value: str):
        if value == "route_me":
            return self.handle_a
        return self.handle_b

    def handle_a(self) -> str:
        self.state.branch = "a"
        return "branch_a"

    def handle_b(self) -> str:
        self.state.branch = "b"
        return "branch_b"


class ErrorPipeline(Cascade):
    """Pipeline that raises in a method."""

    state: CascadeState = CascadeState()

    @initiate
    def boom(self) -> str:
        raise ValueError("deliberate error")


class TestCascadePipeline:
    """Tests for Cascade.execute()."""

    def test_execute_returns_cascade_result(self) -> None:
        """execute() should return a CascadeResult."""
        pipeline = SimplePipeline()
        result = pipeline.execute()
        assert isinstance(result, CascadeResult)

    def test_initiate_method_executed(self) -> None:
        """@initiate method should appear in completed_methods."""
        pipeline = SimplePipeline()
        result = pipeline.execute()
        assert "begin" in result.completed_methods

    def test_observer_method_executed(self) -> None:
        """@observe method should appear in completed_methods."""
        pipeline = SimplePipeline()
        result = pipeline.execute()
        assert "process" in result.completed_methods

    def test_execution_time_recorded(self) -> None:
        """execution_time_ms should be non-negative."""
        pipeline = SimplePipeline()
        result = pipeline.execute()
        assert result.execution_time_ms >= 0

    def test_run_id_in_result(self) -> None:
        """run_id should be populated from state."""
        pipeline = SimplePipeline()
        result = pipeline.execute()
        assert result.run_id is not None
        assert isinstance(result.run_id, str)

    def test_final_state_captured(self) -> None:
        """final_state should be a dict snapshot."""
        pipeline = SimplePipeline()
        result = pipeline.execute()
        assert isinstance(result.final_state, dict)

    def test_routing_follows_correct_branch(self) -> None:
        """@route method should direct execution to the returned branch."""
        pipeline = RoutingPipeline()
        result = pipeline.execute()
        assert "handle_a" in result.completed_methods
        assert "handle_b" not in result.completed_methods

    def test_error_in_method_raises_cascade_execution_error(
        self,
    ) -> None:
        """A method that raises should produce CascadeExecutionError."""
        pipeline = ErrorPipeline()
        with pytest.raises(CascadeExecutionError):
            pipeline.execute()

    def test_build_execution_graph(self) -> None:
        """_build_execution_graph should return a dict."""
        pipeline = SimplePipeline()
        graph = pipeline._build_execution_graph()
        assert isinstance(graph, dict)
        assert "begin" in graph

    def test_multiple_initiate_methods_all_executed(self) -> None:
        """All @initiate methods should run when execute() is called."""

        class MultiInitPipeline(Cascade):
            state: CascadeState = CascadeState()

            @initiate
            def step_a(self) -> str:
                return "a"

            @initiate
            def step_b(self) -> str:
                return "b"

        pipeline = MultiInitPipeline()
        result = pipeline.execute()
        assert "step_a" in result.completed_methods
        assert "step_b" in result.completed_methods
