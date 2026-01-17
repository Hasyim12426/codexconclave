"""Cascade base class — event-driven pipeline orchestration.

Cascade provides a decorator-based model for building deterministic
workflows where each method declares its dependencies via
:func:`~codexconclave.cascade.decorators.observe`.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from codexconclave.cascade.decorators import (
    INITIATE_TAG,
    OBSERVE_TAG,
    OBSERVE_TARGETS,
    ROUTE_TAG,
)
from codexconclave.cascade.state import CascadeState, UnstructuredCascadeState
from codexconclave.signals.bus import SignalBus
from codexconclave.signals.types import (
    CascadeCompletedSignal,
    CascadeStartedSignal,
)

logger = logging.getLogger(__name__)


class CascadeResult(BaseModel):
    """Captures the outcome of a Cascade pipeline execution.

    Attributes:
        run_id: Unique identifier for this pipeline run.
        completed_methods: Names of all methods that executed.
        final_state: Snapshot of the state at completion.
        execution_time_ms: Total wall-clock time in milliseconds.
    """

    run_id: str
    completed_methods: list[str] = Field(default_factory=list)
    final_state: dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float = 0.0


class CascadeExecutionError(RuntimeError):
    """Raised when a Cascade pipeline method fails."""


class Cascade:
    """Base class for event-driven pipeline workflows.

    Subclass this and use :func:`~cascade.decorators.initiate`,
    :func:`~cascade.decorators.observe`, and
    :func:`~cascade.decorators.route` decorators to declare the
    execution graph.

    The pipeline executes starting from all ``@initiate`` methods and
    propagates through ``@observe`` relationships, passing method
    return values as inputs to downstream methods.

    Example::

        class ResearchPipeline(Cascade):
            state = MyState()

            @initiate
            def start(self):
                return "What is AI?"

            @observe(start)
            def answer(self, question: str):
                self.state.answer = f"AI is... ({question})"

            @observe(answer)
            def format_output(self, answer: str):
                self.state.final = answer.upper()
    """

    state: CascadeState

    # Populated by __init_subclass__
    _initiate_methods: list[str] = []
    _observe_map: dict[str, list[str]] = {}  # target -> [observer]
    _route_methods: list[str] = []
    _all_cascade_methods: list[str] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Introspect decorator metadata when a subclass is defined."""
        super().__init_subclass__(**kwargs)
        cls._register_methods()

    def __init__(self, **kwargs: Any) -> None:
        """Initialise the Cascade and set up default state if needed."""
        # Allow state to be passed or default to UnstructuredCascadeState
        if not hasattr(self, "state") or self.state is None:
            self.state = UnstructuredCascadeState()
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    def _register_methods(cls) -> None:
        """Introspect and register @initiate, @observe, @route methods.

        Builds the internal method registry used by the executor.
        """
        initiate_methods: list[str] = []
        observe_map: dict[str, list[str]] = {}
        route_methods: list[str] = []
        all_methods: list[str] = []

        for name, member in inspect.getmembers(cls, predicate=callable):
            if name.startswith("_"):
                continue

            if getattr(member, INITIATE_TAG, False):
                initiate_methods.append(name)
                all_methods.append(name)

            if getattr(member, OBSERVE_TAG, False):
                targets = getattr(member, OBSERVE_TARGETS, ())
                for target in targets:
                    if isinstance(target, tuple):
                        # and_() or or_() sentinel
                        _op, conditions = target
                        for cond in conditions:
                            tname = (
                                cond.__name__ if callable(cond) else str(cond)
                            )
                            observe_map.setdefault(tname, []).append(name)
                    else:
                        # Normalise: callable → its __name__, else str
                        tname = (
                            target.__name__
                            if callable(target)
                            else str(target)
                        )
                        observe_map.setdefault(tname, []).append(name)
                if name not in all_methods:
                    all_methods.append(name)

            if getattr(member, ROUTE_TAG, False):
                route_methods.append(name)
                if name not in all_methods:
                    all_methods.append(name)

        cls._initiate_methods = initiate_methods
        cls._observe_map = observe_map
        cls._route_methods = route_methods
        cls._all_cascade_methods = all_methods

    # ------------------------------------------------------------------
    # Public execution API
    # ------------------------------------------------------------------

    def execute(self) -> CascadeResult:
        """Run the pipeline from all @initiate methods.

        Returns:
            CascadeResult: Result including run metadata and final state.

        Raises:
            CascadeExecutionError: When a method raises an exception.
        """
        start_time = time.monotonic()
        completed: list[str] = []
        method_outputs: dict[str, Any] = {}

        run_id = getattr(self.state, "run_id", "unknown")

        self._emit_started_signals()

        # Execute all initiate methods
        for method_name in self._initiate_methods:
            output = self._execute_method(method_name, None)
            method_outputs[method_name] = output
            completed.append(method_name)
            self._emit_completed_signal(method_name)

            # Propagate to observers
            self._propagate(
                method_name=method_name,
                output=output,
                method_outputs=method_outputs,
                completed=completed,
            )

        elapsed_ms = (time.monotonic() - start_time) * 1000
        final_state = self._capture_state()

        return CascadeResult(
            run_id=run_id,
            completed_methods=completed,
            final_state=final_state,
            execution_time_ms=elapsed_ms,
        )

    async def aexecute(self) -> CascadeResult:
        """Execute the pipeline asynchronously.

        Runs the synchronous pipeline in a thread executor to avoid
        blocking the event loop for sync-only method implementations.

        Returns:
            CascadeResult: Result including run metadata and final state.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.execute)

    # ------------------------------------------------------------------
    # Internal execution helpers
    # ------------------------------------------------------------------

    def _propagate(
        self,
        method_name: str,
        output: Any,
        method_outputs: dict[str, Any],
        completed: list[str],
    ) -> None:
        """Recursively execute all observers of ``method_name``.

        Args:
            method_name: The method whose observers should run.
            output: The output of ``method_name``.
            method_outputs: Accumulator for all method outputs.
            completed: Accumulator for completed method names.
        """
        observers = self._observe_map.get(method_name, [])

        for observer_name in observers:
            if observer_name in completed:
                continue

            obs_output = self._execute_method(observer_name, output)
            method_outputs[observer_name] = obs_output
            completed.append(observer_name)
            self._emit_completed_signal(observer_name)

            # Handle router methods
            if observer_name in self._route_methods and obs_output is not None:
                self._follow_route(
                    route_output=obs_output,
                    method_outputs=method_outputs,
                    completed=completed,
                )
            else:
                self._propagate(
                    method_name=observer_name,
                    output=obs_output,
                    method_outputs=method_outputs,
                    completed=completed,
                )

    def _follow_route(
        self,
        route_output: Any,
        method_outputs: dict[str, Any],
        completed: list[str],
    ) -> None:
        """Execute the method(s) returned by a router.

        Args:
            route_output: The value returned by the router method.
                Should be a callable, list of callables, or ``None``.
            method_outputs: Accumulator for all method outputs.
            completed: Accumulator for completed method names.
        """
        if route_output is None:
            return

        targets: list[Any] = (
            route_output if isinstance(route_output, list) else [route_output]
        )

        for target in targets:
            if callable(target):
                name = target.__name__
            elif isinstance(target, str):
                name = target
            else:
                continue

            if name in completed:
                continue

            output = self._execute_method(name, None)
            method_outputs[name] = output
            completed.append(name)
            self._emit_completed_signal(name)

            self._propagate(
                method_name=name,
                output=output,
                method_outputs=method_outputs,
                completed=completed,
            )

    def _execute_method(self, method_name: str, input_data: Any) -> Any:
        """Execute a single pipeline method, passing input if accepted.

        Args:
            method_name: Name of the method to execute.
            input_data: Value to pass as the first argument (if the
                method accepts one beyond ``self``).

        Returns:
            Any: The return value of the method.

        Raises:
            CascadeExecutionError: When the method raises an exception.
        """
        method = getattr(self, method_name, None)
        if method is None:
            raise CascadeExecutionError(
                f"Cascade method '{method_name}' not found on "
                f"{type(self).__name__}."
            )

        sig = inspect.signature(method)
        params = [p for p in sig.parameters.values() if p.name != "self"]

        try:
            if input_data is not None and params:
                return method(input_data)
            return method()
        except Exception as exc:
            raise CascadeExecutionError(
                f"Cascade method '{method_name}' raised: {exc}"
            ) from exc

    def _build_execution_graph(self) -> dict[str, list[str]]:
        """Build method dependency graph from decorator metadata.

        Returns:
            dict[str, list[str]]: Mapping of method name to its
                downstream observers.
        """
        graph: dict[str, list[str]] = {}

        for method_name in self._all_cascade_methods:
            graph[method_name] = list(self._observe_map.get(method_name, []))

        return graph

    def _capture_state(self) -> dict[str, Any]:
        """Capture the current state as a plain dictionary.

        Returns:
            dict[str, Any]: A snapshot of the pipeline state.
        """
        if self.state is None:
            return {}
        try:
            return self.state.model_dump()
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _emit_started_signals(self) -> None:
        """Emit :class:`CascadeStartedSignal` for all initiate methods."""
        for method_name in self._initiate_methods:
            try:
                SignalBus.instance().emit(
                    CascadeStartedSignal(method_name=method_name)
                )
            except Exception:
                logger.debug(
                    "Failed to emit CascadeStartedSignal",
                    exc_info=True,
                )

    def _emit_completed_signal(self, method_name: str) -> None:
        """Emit :class:`CascadeCompletedSignal` for ``method_name``.

        Args:
            method_name: The method that just completed.
        """
        try:
            SignalBus.instance().emit(
                CascadeCompletedSignal(method_name=method_name)
            )
        except Exception:
            logger.debug(
                "Failed to emit CascadeCompletedSignal", exc_info=True
            )
