"""Conclave — the main orchestration class for CodexConclave.

A :class:`Conclave` assembles a team of :class:`~codexconclave.arbiter.core.Arbiter`
instances and executes a sequence of :class:`~codexconclave.directive.Directive`
objects according to the configured :class:`~codexconclave.protocol.Protocol`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

from codexconclave.arbiter.core import Arbiter, ArbiterResult
from codexconclave.directive import Directive, DirectiveResult
from codexconclave.llm.provider import LLMProvider
from codexconclave.protocol import Protocol
from codexconclave.signals.bus import SignalBus
from codexconclave.signals.types import (
    ConclaveCompletedSignal,
    ConclaveErrorSignal,
    ConclaveStartedSignal,
    DirectiveCompletedSignal,
    DirectiveStartedSignal,
)

logger = logging.getLogger(__name__)

_MANAGER_SYSTEM = """\
You are the manager of a team of AI agents called Arbiters.
Your team consists of the following Arbiters:
{arbiter_list}

When given a task, decide which Arbiter should handle it and
respond with JSON:
{{"assign_to": "<arbiter_role>", "directive": "<task description>"}}

If the task is complete, respond with JSON:
{{"complete": true, "summary": "<final summary>"}}
"""


class ConclaveResult(BaseModel):
    """The aggregated output of a completed Conclave execution.

    Attributes:
        directive_results: Ordered list of individual directive results.
        final_output: The output of the last completed directive.
        token_usage: Aggregated token counts across all LLM calls.
    """

    directive_results: list[DirectiveResult]
    final_output: str
    token_usage: dict[str, int] = Field(default_factory=dict)

    def __str__(self) -> str:
        """Return the final output when converting to string."""
        return self.final_output


class ConclaveConfigError(ValueError):
    """Raised when a Conclave is misconfigured."""


class Conclave(BaseModel):
    """Orchestrates a team of Arbiters to accomplish complex objectives.

    The Conclave is the top-level execution unit.  It validates
    configuration, wires up Arbiters, dispatches Directives according
    to the selected :class:`Protocol`, and aggregates results into a
    :class:`ConclaveResult`.

    Example::

        conclave = Conclave(
            arbiters=[researcher, writer],
            directives=[research_task, write_task],
            protocol=Protocol.sequential,
        )
        result = conclave.assemble()
        print(result)
    """

    arbiters: list[Arbiter]
    """The Arbiters participating in this Conclave."""

    directives: list[Directive]
    """The ordered list of Directives to execute."""

    protocol: Protocol = Protocol.sequential
    """Execution strategy: sequential or hierarchical."""

    verbose: bool = False
    """When ``True``, progress messages are printed to stdout."""

    memory_enabled: bool = False
    """When ``True``, Arbiters share a Chronicle memory store."""

    knowledge_sources: list[Any] = Field(default_factory=list)
    """Optional Codex knowledge sources injected as context."""

    manager_llm: LLMProvider | None = None
    """LLM used by the manager Arbiter in hierarchical mode."""

    manager_arbiter: Arbiter | None = None
    """Custom manager Arbiter for hierarchical mode.  When ``None``,
    one is auto-created from :attr:`manager_llm`."""

    max_retries: int = 3
    """Number of times to retry a failed directive."""

    share_telemetry: bool = True
    """Whether to share anonymised telemetry for framework improvement."""

    output_log_file: str | None = None
    """Path to a file where execution logs should be written."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ------------------------------------------------------------------
    # Public execution API
    # ------------------------------------------------------------------

    def assemble(self) -> ConclaveResult:
        """Execute all directives and return the combined result.

        Returns:
            ConclaveResult: Aggregated results of all directives.

        Raises:
            ConclaveConfigError: On configuration errors.
            RuntimeError: When execution fails after all retries.
        """
        self._validate()
        self._wire_delegation()

        start_time = time.monotonic()
        self._emit_started()

        try:
            if self.protocol == Protocol.sequential:
                results = self._run_sequential()
            else:
                results = self._run_hierarchical()
        except Exception as exc:
            self._emit_error(exc)
            raise

        conclave_result = self._build_result(results)
        self._emit_completed(conclave_result)

        elapsed = time.monotonic() - start_time
        logger.info(
            "Conclave completed in %.2fs with %d directive(s).",
            elapsed,
            len(results),
        )

        if self.output_log_file:
            self._write_log(conclave_result)

        return conclave_result

    async def aassemble(self) -> ConclaveResult:
        """Execute all directives asynchronously.

        Returns:
            ConclaveResult: Aggregated results of all directives.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.assemble)

    # ------------------------------------------------------------------
    # Sequential execution
    # ------------------------------------------------------------------

    def _run_sequential(self) -> list[DirectiveResult]:
        """Execute directives one after another.

        Each directive's output is available as context to subsequent
        directives.

        Returns:
            list[DirectiveResult]: Results in execution order.
        """
        results: list[DirectiveResult] = []

        for directive in self.directives:
            arbiter = self._resolve_arbiter(directive)
            context = self._build_context(directive, results)

            directive_result = self._execute_directive(
                directive=directive,
                arbiter=arbiter,
                context=context,
            )
            results.append(directive_result)
            directive.mark_complete(directive_result)

        return results

    # ------------------------------------------------------------------
    # Hierarchical execution
    # ------------------------------------------------------------------

    def _run_hierarchical(self) -> list[DirectiveResult]:
        """Execute directives with a manager coordinating Arbiters.

        The manager Arbiter decides which Arbiter handles each task
        and collects outputs until all directives are satisfied.

        Returns:
            list[DirectiveResult]: Results in completion order.
        """
        manager = self._get_or_create_manager()
        results: list[DirectiveResult] = []

        for directive in self.directives:
            context = self._build_context(directive, results)

            # Ask manager to assign
            assigned_arbiter = self._manager_assign(
                manager, directive, context
            )
            if assigned_arbiter is None:
                # Fall back to first available Arbiter
                assigned_arbiter = self.arbiters[0]
                logger.warning(
                    "Manager failed to assign '%s'; falling back to '%s'.",
                    directive.description[:60],
                    assigned_arbiter.role,
                )

            directive_result = self._execute_directive(
                directive=directive,
                arbiter=assigned_arbiter,
                context=context,
            )
            results.append(directive_result)
            directive.mark_complete(directive_result)

        return results

    def _manager_assign(
        self,
        manager: Arbiter,
        directive: Directive,
        context: str | None,
    ) -> Arbiter | None:
        """Ask the manager to assign an Arbiter to ``directive``.

        Args:
            manager: The manager Arbiter.
            directive: The directive to assign.
            context: Current context string.

        Returns:
            Optional[Arbiter]: The chosen Arbiter, or ``None`` if
                assignment fails.
        """
        import json as _json

        arbiter_list = "\n".join(
            f"- {a.role}: {a.objective}" for a in self.arbiters
        )
        system_prompt = _MANAGER_SYSTEM.format(arbiter_list=arbiter_list)

        user_message = (
            f"Directive: {directive.description}\n"
            f"Expected output: {directive.expected_output}\n"
        )
        if context:
            user_message += f"\nContext:\n{context}\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            raw = manager.llm.complete(messages=messages)
            start = raw.find("{")
            end = raw.rfind("}")
            if start == -1 or end == -1:
                return None
            parsed = _json.loads(raw[start : end + 1])
            role = parsed.get("assign_to", "")
            for arbiter in self.arbiters:
                if arbiter.role.lower() == role.lower():
                    return arbiter
        except Exception as exc:
            logger.warning("Manager assignment failed: %s", exc)

        return None

    def _get_or_create_manager(self) -> Arbiter:
        """Return the manager Arbiter for hierarchical execution.

        Returns:
            Arbiter: An existing or auto-created manager.
        """
        if self.manager_arbiter is not None:
            return self.manager_arbiter

        llm = self.manager_llm or (
            self.arbiters[0].llm if self.arbiters else LLMProvider()
        )

        return Arbiter(
            role="Manager",
            objective=(
                "Coordinate the team and delegate tasks to the "
                "most suitable Arbiter."
            ),
            llm=llm,
            verbose=self.verbose,
        )

    # ------------------------------------------------------------------
    # Directive execution with retry
    # ------------------------------------------------------------------

    def _execute_directive(
        self,
        directive: Directive,
        arbiter: Arbiter,
        context: str | None,
    ) -> DirectiveResult:
        """Execute a single directive with retry logic.

        Args:
            directive: The directive to execute.
            arbiter: The Arbiter to use.
            context: Accumulated context string.

        Returns:
            DirectiveResult: The result after successful execution.

        Raises:
            RuntimeError: When all retries are exhausted.
        """
        self._emit_directive_started(directive, arbiter)

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                arbiter_result: ArbiterResult = arbiter.perform(
                    directive=directive, context=context
                )
                result = DirectiveResult(
                    description=directive.description,
                    expected_output=directive.expected_output,
                    raw_output=arbiter_result.raw_output,
                    output=arbiter_result.output,
                    agent_role=arbiter_result.arbiter_role,
                    structured_output=arbiter_result.structured_output,
                    output_file=directive.output_file,
                )
                self._emit_directive_completed(directive, result)

                if self.verbose:
                    logger.info(
                        "[%s] Completed directive: %s",
                        arbiter.role,
                        directive.description[:60],
                    )

                return result

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Directive attempt %d/%d failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(1)

        raise RuntimeError(
            f"Directive '{directive.description[:60]}' failed after "
            f"{self.max_retries} attempts."
        ) from last_error

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    def _build_context(
        self,
        directive: Directive,
        results: list[DirectiveResult],
    ) -> str | None:
        """Build a context string from previously completed results.

        Args:
            directive: The upcoming directive (unused currently but
                reserved for filtering logic).
            results: All results completed so far.

        Returns:
            Optional[str]: Formatted context string or ``None``.
        """
        if not results:
            return None

        parts: list[str] = []
        for r in results:
            snippet = r.output[:1000]
            parts.append(
                f"[{r.agent_role} — {r.description[:60]}]:\n{snippet}"
            )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Result assembly
    # ------------------------------------------------------------------

    def _build_result(self, results: list[DirectiveResult]) -> ConclaveResult:
        """Combine directive results into a :class:`ConclaveResult`.

        Args:
            results: Completed directive results.

        Returns:
            ConclaveResult: The aggregated result.
        """
        final_output = results[-1].output if results else ""
        return ConclaveResult(
            directive_results=results,
            final_output=final_output,
        )

    # ------------------------------------------------------------------
    # Arbiter resolution
    # ------------------------------------------------------------------

    def _resolve_arbiter(self, directive: Directive) -> Arbiter:
        """Determine which Arbiter should execute ``directive``.

        If the directive has an explicit arbiter, that is used.
        Otherwise, Arbiters are round-robined.

        Args:
            directive: The directive needing an Arbiter.

        Returns:
            Arbiter: The assigned Arbiter.

        Raises:
            ConclaveConfigError: When no Arbiter can be resolved.
        """
        if directive.arbiter is not None:
            return cast(Arbiter, directive.arbiter)

        if not self.arbiters:
            raise ConclaveConfigError(
                "No Arbiters available and directive has no assigned Arbiter."
            )

        # Round-robin: assign based on directive index
        idx = self.directives.index(directive) % len(self.arbiters)
        return self.arbiters[idx]

    # ------------------------------------------------------------------
    # Validation and wiring
    # ------------------------------------------------------------------

    def _validate(self) -> None:
        """Validate Conclave configuration before execution.

        Raises:
            ConclaveConfigError: On invalid configuration.
        """
        if not self.directives:
            raise ConclaveConfigError(
                "A Conclave must have at least one Directive."
            )
        if not self.arbiters:
            raise ConclaveConfigError(
                "A Conclave must have at least one Arbiter."
            )
        if (
            self.protocol == Protocol.hierarchical
            and self.manager_llm is None
            and self.manager_arbiter is None
        ):
            logger.info(
                "Hierarchical protocol: using first Arbiter's LLM "
                "for the manager."
            )

    def _wire_delegation(self) -> None:
        """Inject peer Arbiter lists for delegation support."""
        for arbiter in self.arbiters:
            arbiter.peer_arbiters = [
                a for a in self.arbiters if a is not arbiter
            ]

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _write_log(self, result: ConclaveResult) -> None:
        """Write the final result to :attr:`output_log_file`.

        Args:
            result: The conclave result to log.
        """
        if self.output_log_file is None:
            return
        try:
            with open(self.output_log_file, "w", encoding="utf-8") as fh:
                fh.write(str(result))
            logger.debug(
                "Wrote conclave output log to %s",
                self.output_log_file,
            )
        except OSError as exc:
            logger.warning(
                "Failed to write log file '%s': %s",
                self.output_log_file,
                exc,
            )

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _emit_started(self) -> None:
        """Emit :class:`ConclaveStartedSignal`."""
        try:
            SignalBus.instance().emit(
                ConclaveStartedSignal(
                    directive_count=len(self.directives),
                    arbiter_count=len(self.arbiters),
                )
            )
        except Exception:
            logger.debug("Failed to emit ConclaveStartedSignal", exc_info=True)

    def _emit_completed(self, result: ConclaveResult) -> None:
        """Emit :class:`ConclaveCompletedSignal`.

        Args:
            result: The completed result to summarise.
        """
        try:
            SignalBus.instance().emit(
                ConclaveCompletedSignal(
                    result_summary=result.final_output[:500]
                )
            )
        except Exception:
            logger.debug(
                "Failed to emit ConclaveCompletedSignal",
                exc_info=True,
            )

    def _emit_error(self, exc: Exception) -> None:
        """Emit :class:`ConclaveErrorSignal`.

        Args:
            exc: The exception that caused the failure.
        """
        try:
            SignalBus.instance().emit(ConclaveErrorSignal(error=str(exc)))
        except Exception:
            logger.debug("Failed to emit ConclaveErrorSignal", exc_info=True)

    def _emit_directive_started(
        self, directive: Directive, arbiter: Arbiter
    ) -> None:
        """Emit :class:`DirectiveStartedSignal`.

        Args:
            directive: The directive being started.
            arbiter: The executing Arbiter.
        """
        try:
            SignalBus.instance().emit(
                DirectiveStartedSignal(
                    directive_description=directive.description,
                    arbiter_role=arbiter.role,
                )
            )
        except Exception:
            logger.debug(
                "Failed to emit DirectiveStartedSignal", exc_info=True
            )

    def _emit_directive_completed(
        self,
        directive: Directive,
        result: DirectiveResult,
    ) -> None:
        """Emit :class:`DirectiveCompletedSignal`.

        Args:
            directive: The completed directive.
            result: The directive result.
        """
        try:
            SignalBus.instance().emit(
                DirectiveCompletedSignal(
                    directive_description=directive.description,
                    output=result.output[:500],
                )
            )
        except Exception:
            logger.debug(
                "Failed to emit DirectiveCompletedSignal",
                exc_info=True,
            )
