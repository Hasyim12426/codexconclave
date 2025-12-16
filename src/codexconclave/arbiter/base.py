"""Abstract base class defining the Arbiter interface."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from codexconclave.instruments.base import BaseInstrument
from codexconclave.llm.provider import LLMProvider

if TYPE_CHECKING:
    from codexconclave.arbiter.core import ArbiterResult
    from codexconclave.directive import Directive

logger = logging.getLogger(__name__)


class BaseArbiter(BaseModel, ABC):
    """Abstract base defining the Arbiter (AI agent) interface.

    An Arbiter is an autonomous AI agent that uses an LLM and optional
    Instruments to perform :class:`~codexconclave.directive.Directive`
    work units.

    Subclass this to create custom Arbiter implementations.  The
    primary method to implement is :meth:`perform`.
    """

    role: str
    """A concise label describing what this Arbiter does (e.g. "Research Analyst")."""

    objective: str
    """The Arbiter's primary goal — used to build its system prompt."""

    persona: str = ""
    """Background / backstory that shapes the Arbiter's communication
    style and reasoning approach."""

    llm: Any = Field(default_factory=LLMProvider)
    """The LLM provider this Arbiter will use for completions.

    Accepts any object that implements the LLMProvider interface
    (``complete``, ``model``, ``context_window``), including mocks
    used in testing.
    """

    instruments: list[BaseInstrument] = Field(default_factory=list)
    """Instruments (tools) this Arbiter can invoke."""

    verbose: bool = False
    """When ``True``, detailed execution logs are printed."""

    allow_delegation: bool = False
    """When ``True``, this Arbiter may delegate sub-tasks to other
    Arbiters registered in the same Conclave."""

    max_iterations: int = 20
    """Maximum number of LLM ↔ tool calling loops before giving up."""

    max_execution_time: float | None = None
    """Wall-clock time limit in seconds.  ``None`` means no limit."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @abstractmethod
    def perform(
        self,
        directive: Directive,
        context: str | None = None,
    ) -> ArbiterResult:
        """Execute ``directive`` and return the result.

        Args:
            directive: The unit of work to perform.
            context: Optional context string from previously completed
                directives.

        Returns:
            ArbiterResult: Structured result of the execution.
        """
