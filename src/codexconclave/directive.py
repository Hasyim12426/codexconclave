"""Directive — the unit of work in a CodexConclave Conclave.

A :class:`Directive` describes what needs to be done, who should do
it, what format is expected, and any pre/post processing hooks.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from codexconclave.instruments.base import BaseInstrument

logger = logging.getLogger(__name__)


class DirectiveResult(BaseModel):
    """Captures the completed output of a single Directive.

    Attributes:
        description: The directive's original description.
        expected_output: What the directive aimed to produce.
        raw_output: The unprocessed LLM response.
        output: The cleaned / post-processed final output.
        agent_role: Role of the Arbiter that completed this.
        structured_output: Optional parsed structured data.
        output_file: Path where the output was written, if any.
    """

    description: str
    expected_output: str
    raw_output: str
    output: str
    agent_role: str
    structured_output: Any | None = None
    output_file: str | None = None


class Directive(BaseModel):
    """Defines a unit of work to be performed by an Arbiter.

    Directives are the atomic work units of a :class:`Conclave`.  Each
    directive has a natural-language description, an expected output
    specification, and an optional set of instruments and context
    directives that enrich the Arbiter's reasoning.

    Example::

        directive = Directive(
            description="Summarise recent AI research papers.",
            expected_output="A 500-word executive summary.",
            arbiter=research_arbiter,
        )
    """

    description: str
    """Natural-language description of the work to be done."""

    expected_output: str
    """Specification of what a correct output looks like."""

    arbiter: Any | None = None
    """The Arbiter responsible for completing this directive.
    Can be ``None`` when the Conclave assigns Arbiters automatically."""

    context: list[Directive] = Field(default_factory=list)
    """Other directives whose outputs should be injected as context."""

    instruments: list[BaseInstrument] = Field(default_factory=list)
    """Extra instruments available *only* for this directive."""

    async_execution: bool = False
    """When ``True``, this directive may execute concurrently."""

    output_format: type[BaseModel] | None = None
    """Optional Pydantic model class.  When set, the Arbiter's output
    is parsed and validated into this model."""

    output_file: str | None = None
    """File path where the output should be persisted."""

    callback: Callable[[DirectiveResult], None] | None = None
    """Optional callback invoked with the result after completion."""

    guardrail: Callable[[str], tuple[bool, str]] | None = None
    """Optional function ``(output) -> (passed, cleaned_output)``.
    When ``passed`` is ``False``, the output is flagged but still used."""

    # Internal: populated after execution (not part of public schema)
    _result: DirectiveResult | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def mark_complete(self, result: DirectiveResult) -> None:
        """Record the result after successful execution.

        This is called internally by the Conclave executor.  It stores
        the result so linked directives can surface it as context, and
        invokes any registered :attr:`callback`.

        Args:
            result: The completed directive result.
        """
        object.__setattr__(self, "_result", result)
        if self.callback is not None:
            try:
                self.callback(result)
            except Exception as exc:
                logger.warning(
                    "Directive callback raised an exception: %s", exc
                )

    @property
    def result(self) -> DirectiveResult | None:
        """Return the completed result, or ``None`` if not yet done.

        Returns:
            Optional[DirectiveResult]: The result or ``None``.
        """
        return self._result
