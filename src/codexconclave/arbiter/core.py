"""Core Arbiter implementation for CodexConclave.

This module provides the fully-featured :class:`Arbiter` class which
drives autonomous AI agent execution including tool-calling loops,
delegation, memory integration, and observability signals.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel

from codexconclave.arbiter.base import BaseArbiter
from codexconclave.instruments.base import (
    BaseInstrument,
    InstrumentExecutionError,
)
from codexconclave.signals.bus import SignalBus
from codexconclave.signals.types import (
    ArbiterCompletedSignal,
    ArbiterErrorSignal,
    ArbiterStartedSignal,
)

if TYPE_CHECKING:
    from codexconclave.directive import Directive

logger = logging.getLogger(__name__)

_SYSTEM_TEMPLATE = """\
You are {role}.

Objective: {objective}

{persona_section}
{instruments_section}
You must complete the task described by the user.
When you are ready to give your final answer, respond with the text
of your answer directly — do not wrap it in JSON or markdown unless
the task requires it.
"""

_INSTRUMENTS_SECTION = """\
You have access to the following instruments (tools):
{tool_list}

To use an instrument, respond with a JSON block in this format:
{{
  "instrument": "<instrument_name>",
  "arguments": {{<key>: <value>, ...}}
}}

After receiving the instrument result, continue your reasoning.
"""


class ArbiterResult(BaseModel):
    """Captures the outcome of an Arbiter's directive execution.

    Attributes:
        output: The final human-readable output.
        directive_description: Description of the executed directive.
        arbiter_role: Role label of the Arbiter that produced this.
        raw_output: The unprocessed last LLM response.
        structured_output: Optional parsed structured data.
        iterations: Number of LLM/tool loops executed.
        execution_time_ms: Total wall-clock time in milliseconds.
    """

    output: str
    directive_description: str
    arbiter_role: str
    raw_output: str
    structured_output: Any | None = None
    iterations: int = 0
    execution_time_ms: float = 0.0


class Arbiter(BaseArbiter):
    """Autonomous AI agent that executes Directives using LLM reasoning.

    The Arbiter drives a multi-turn loop:
    1. Build a system prompt from role / objective / persona.
    2. Call the LLM with the directive and available instruments.
    3. If the LLM requests an instrument, execute it and feed back
       the result.
    4. Repeat until the LLM gives a final answer, the iteration limit
       is reached, or the time limit expires.

    Delegation is supported when :attr:`allow_delegation` is ``True``
    and :attr:`peer_arbiters` is populated (injected by the Conclave).
    """

    peer_arbiters: list[Arbiter] = []
    """Other Arbiters this one may delegate to.  Set by the Conclave."""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def perform(
        self,
        directive: Directive,
        context: str | None = None,
    ) -> ArbiterResult:
        """Execute ``directive`` using the LLM + tool-calling loop.

        Args:
            directive: The unit of work to execute.
            context: Optional context string from prior directives.

        Returns:
            ArbiterResult: The structured result of execution.

        Raises:
            RuntimeError: When the Arbiter exceeds iteration or time
                limits without producing a final answer.
        """
        start_time = time.monotonic()

        self._emit_started(directive)

        try:
            result = self._execute_loop(
                directive=directive,
                context=context,
                start_time=start_time,
            )
        except Exception as exc:
            self._emit_error(directive, exc)
            raise

        self._emit_completed(directive, result)
        return result

    # ------------------------------------------------------------------
    # Execution loop
    # ------------------------------------------------------------------

    def _execute_loop(
        self,
        directive: Directive,
        context: str | None,
        start_time: float,
    ) -> ArbiterResult:
        """Run the iterative LLM → instrument → LLM loop.

        Args:
            directive: The directive to execute.
            context: Prior directive context.
            start_time: Monotonic start time for timeout tracking.

        Returns:
            ArbiterResult: The final result.
        """
        all_instruments = list(self.instruments) + list(directive.instruments)
        instrument_map = {i.name: i for i in all_instruments}

        messages = self._build_messages(
            directive=directive,
            context=context,
            instruments=all_instruments,
        )

        iterations = 0
        raw_output = ""

        while iterations < self.max_iterations:
            self._check_time_limit(start_time)

            tool_schemas = [
                i.to_tool_schema() for i in all_instruments
            ] or None

            raw_output = self.llm.complete(
                messages=messages,
                tools=tool_schemas,
            )
            # Re-check after a potentially slow LLM call
            self._check_time_limit(start_time)

            if self.verbose:
                logger.info(
                    "[%s] Iteration %d response: %s",
                    self.role,
                    iterations + 1,
                    raw_output[:300],
                )

            # Check for structured output if directive specifies it
            if directive.output_format is not None and iterations == 0:
                try:
                    structured = directive.output_format.model_validate_json(
                        raw_output
                    )
                    elapsed_ms = (time.monotonic() - start_time) * 1000
                    return ArbiterResult(
                        output=raw_output,
                        directive_description=directive.description,
                        arbiter_role=self.role,
                        raw_output=raw_output,
                        structured_output=structured,
                        iterations=iterations + 1,
                        execution_time_ms=elapsed_ms,
                    )
                except Exception:
                    pass

            # Detect instrument call
            instrument_call = self._parse_instrument_call(raw_output)
            if instrument_call is not None:
                inst_name = instrument_call.get("instrument", "")
                inst_args = instrument_call.get("arguments", {})

                instrument = instrument_map.get(inst_name)
                if instrument is not None:
                    inst_result = self._invoke_instrument(
                        instrument, inst_args
                    )

                    # Check if result_as_answer
                    if instrument.result_as_answer:
                        elapsed_ms = (time.monotonic() - start_time) * 1000
                        return ArbiterResult(
                            output=inst_result,
                            directive_description=directive.description,
                            arbiter_role=self.role,
                            raw_output=raw_output,
                            iterations=iterations + 1,
                            execution_time_ms=elapsed_ms,
                        )

                    messages.append(
                        {"role": "assistant", "content": raw_output}
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Instrument '{inst_name}' result:\n"
                                f"{inst_result}\n\nContinue your work."
                            ),
                        }
                    )
                    iterations += 1
                    continue
                else:
                    # Unknown instrument — treat as final answer
                    logger.warning(
                        "Unknown instrument '%s' requested by %s",
                        inst_name,
                        self.role,
                    )

            # Check delegation
            if self.allow_delegation and self.peer_arbiters:
                delegation = self._parse_delegation(raw_output)
                if delegation is not None:
                    delegated_output = self._delegate(delegation, directive)
                    messages.append(
                        {"role": "assistant", "content": raw_output}
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Delegation result:\n{delegated_output}"
                                "\n\nContinue your work."
                            ),
                        }
                    )
                    iterations += 1
                    continue

            # No instrument call — treat as final answer
            break

        elapsed_ms = (time.monotonic() - start_time) * 1000
        output = self._post_process(raw_output, directive)

        if directive.output_file:
            self._write_output_file(directive.output_file, output)

        return ArbiterResult(
            output=output,
            directive_description=directive.description,
            arbiter_role=self.role,
            raw_output=raw_output,
            iterations=iterations + 1,
            execution_time_ms=elapsed_ms,
        )

    # ------------------------------------------------------------------
    # Message construction
    # ------------------------------------------------------------------

    def _build_messages(
        self,
        directive: Directive,
        context: str | None,
        instruments: list[BaseInstrument],
    ) -> list[dict[str, str]]:
        """Construct the initial message list for the LLM.

        Args:
            directive: The directive to execute.
            context: Optional prior-directive context.
            instruments: Available instruments.

        Returns:
            list[dict[str, str]]: OpenAI-style message list.
        """
        system_prompt = self._build_system_prompt(instruments)

        user_content = f"Task: {directive.description}\n"
        user_content += f"Expected output: {directive.expected_output}\n"

        if context:
            user_content += f"\nContext from prior work:\n{context}\n"

        # Inject context from linked directives
        if directive.context:
            linked_context = self._build_directive_context(directive.context)
            if linked_context:
                user_content += f"\nAdditional context:\n{linked_context}\n"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

    def _build_system_prompt(self, instruments: list[BaseInstrument]) -> str:
        """Build the system prompt from role, objective, and persona.

        Args:
            instruments: The instruments available in this execution.

        Returns:
            str: The formatted system prompt.
        """
        persona_section = (
            f"Background: {self.persona}\n" if self.persona else ""
        )

        if instruments:
            tool_list = "\n".join(
                f"- {i.name}: {i.description}" for i in instruments
            )
            instruments_section = _INSTRUMENTS_SECTION.format(
                tool_list=tool_list
            )
        else:
            instruments_section = ""

        return _SYSTEM_TEMPLATE.format(
            role=self.role,
            objective=self.objective,
            persona_section=persona_section,
            instruments_section=instruments_section,
        )

    def _build_directive_context(
        self, linked_directives: list[Directive]
    ) -> str:
        """Summarize output from context-linked directives.

        Args:
            linked_directives: Directives whose output should be
                surfaced as context.

        Returns:
            str: Formatted context string.
        """
        parts: list[str] = []
        for d in linked_directives:
            if hasattr(d, "_result") and d._result is not None:
                parts.append(f"[{d.description[:60]}]: {d._result.output}")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Instrument helpers
    # ------------------------------------------------------------------

    def _parse_instrument_call(self, response: str) -> dict[str, Any] | None:
        """Detect and parse an instrument call in the LLM response.

        The Arbiter looks for a JSON block with ``instrument`` and
        ``arguments`` keys anywhere in the response text.

        Args:
            response: Raw LLM response text.

        Returns:
            Optional[dict]: Parsed call or ``None`` if not found.
        """
        start = response.find("{")
        end = response.rfind("}")
        if start == -1 or end == -1:
            return None

        candidate = response[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if "instrument" in parsed and "arguments" in parsed:
                return cast(dict[str, Any], parsed)
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _invoke_instrument(
        self,
        instrument: BaseInstrument,
        args: dict[str, Any],
    ) -> str:
        """Safely invoke ``instrument`` with ``args``.

        Args:
            instrument: The instrument to invoke.
            args: Keyword arguments for the instrument.

        Returns:
            str: The instrument output or an error message.
        """
        try:
            result = instrument.run(**args)
            return result.output
        except InstrumentExecutionError as exc:
            logger.warning("Instrument '%s' failed: %s", instrument.name, exc)
            return f"[Instrument error: {exc}]"

    # ------------------------------------------------------------------
    # Delegation helpers
    # ------------------------------------------------------------------

    def _parse_delegation(self, response: str) -> dict[str, Any] | None:
        """Detect a delegation request in the LLM response.

        Expected format::

            {"delegate_to": "<role>", "task": "<description>"}

        Args:
            response: Raw LLM response text.

        Returns:
            Optional[dict]: Delegation details or ``None``.
        """
        start = response.find("{")
        end = response.rfind("}")
        if start == -1 or end == -1:
            return None

        candidate = response[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if "delegate_to" in parsed and "task" in parsed:
                return cast(dict[str, Any], parsed)
        except (json.JSONDecodeError, ValueError):
            pass
        return None

    def _delegate(
        self,
        delegation: dict[str, Any],
        original_directive: Directive,
    ) -> str:
        """Find the target Arbiter and have it perform the sub-task.

        Args:
            delegation: Parsed delegation dict with ``delegate_to``
                and ``task`` keys.
            original_directive: The original directive for fallback.

        Returns:
            str: Output from the delegated Arbiter, or an error note.
        """
        from codexconclave.directive import Directive

        target_role = delegation.get("delegate_to", "")
        task_description = delegation.get("task", "")

        for peer in self.peer_arbiters:
            if peer.role.lower() == target_role.lower():
                sub_directive = Directive(
                    description=task_description,
                    expected_output=(f"Complete: {task_description}"),
                    arbiter=peer,
                )
                try:
                    sub_result = peer.perform(sub_directive)
                    return sub_result.output
                except Exception as exc:
                    return f"[Delegation failed: {exc}]"

        return f"[Delegation failed: no Arbiter with role '{target_role}']"

    # ------------------------------------------------------------------
    # Post-processing and output
    # ------------------------------------------------------------------

    def _post_process(self, raw: str, directive: Directive) -> str:
        """Apply guardrails and clean the raw LLM output.

        Args:
            raw: The raw LLM response.
            directive: The directive with optional guardrail.

        Returns:
            str: Processed output text.
        """
        output = raw.strip()

        if directive.guardrail is not None:
            passed, cleaned = directive.guardrail(output)
            if passed:
                output = cleaned
            else:
                logger.warning(
                    "Guardrail rejected output for directive: %s",
                    directive.description[:80],
                )

        return output

    def _write_output_file(self, path: str, content: str) -> None:
        """Write the output to a file on disk.

        Args:
            path: File path to write.
            content: Content to write.
        """
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            logger.debug("Wrote directive output to %s", path)
        except OSError as exc:
            logger.warning("Failed to write output file '%s': %s", path, exc)

    # ------------------------------------------------------------------
    # Time limit
    # ------------------------------------------------------------------

    def _check_time_limit(self, start_time: float) -> None:
        """Raise if the execution time limit has been exceeded.

        Args:
            start_time: Monotonic time when execution began.

        Raises:
            TimeoutError: When the time limit is exceeded.
        """
        if self.max_execution_time is None:
            return
        elapsed = time.monotonic() - start_time
        if elapsed >= self.max_execution_time:
            raise TimeoutError(
                f"Arbiter '{self.role}' exceeded its execution time "
                f"limit of {self.max_execution_time}s "
                f"(elapsed: {elapsed:.1f}s)."
            )

    # ------------------------------------------------------------------
    # Signal helpers
    # ------------------------------------------------------------------

    def _emit_started(self, directive: Directive) -> None:
        """Emit :class:`ArbiterStartedSignal`.

        Args:
            directive: The directive being started.
        """
        try:
            SignalBus.instance().emit(
                ArbiterStartedSignal(
                    arbiter_role=self.role,
                    directive_description=directive.description,
                )
            )
        except Exception:
            logger.debug("Failed to emit ArbiterStartedSignal", exc_info=True)

    def _emit_completed(
        self, directive: Directive, result: ArbiterResult
    ) -> None:
        """Emit :class:`ArbiterCompletedSignal`.

        Args:
            directive: The completed directive.
            result: The result to summarise in the signal.
        """
        try:
            SignalBus.instance().emit(
                ArbiterCompletedSignal(
                    arbiter_role=self.role,
                    output=result.output[:500],
                )
            )
        except Exception:
            logger.debug(
                "Failed to emit ArbiterCompletedSignal", exc_info=True
            )

    def _emit_error(self, directive: Directive, exc: Exception) -> None:
        """Emit :class:`ArbiterErrorSignal`.

        Args:
            directive: The directive that caused the error.
            exc: The exception that was raised.
        """
        try:
            SignalBus.instance().emit(
                ArbiterErrorSignal(
                    arbiter_role=self.role,
                    error=str(exc),
                )
            )
        except Exception:
            logger.debug("Failed to emit ArbiterErrorSignal", exc_info=True)
