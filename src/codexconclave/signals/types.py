"""Signal type definitions for CodexConclave observability.

Signals are emitted throughout the framework lifecycle and can be
consumed by any registered :class:`BaseSignalListener`.  All signal
types are immutable Pydantic models.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class Signal(BaseModel):
    """Base class for all framework signals.

    Every signal carries a unique ``id``, an ISO-8601 ``timestamp``,
    and a ``source`` identifier describing where it originated.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "codexconclave"

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Arbiter signals
# ---------------------------------------------------------------------------


class ArbiterSignal(Signal):
    """Base class for signals related to Arbiter lifecycle events."""


class ArbiterStartedSignal(ArbiterSignal):
    """Emitted when an Arbiter begins working on a Directive.

    Attributes:
        arbiter_role: The role label of the Arbiter.
        directive_description: The description of the assigned
            Directive.
    """

    arbiter_role: str
    directive_description: str


class ArbiterCompletedSignal(ArbiterSignal):
    """Emitted when an Arbiter successfully completes a Directive.

    Attributes:
        arbiter_role: The role label of the Arbiter.
        output: The textual output produced by the Arbiter.
    """

    arbiter_role: str
    output: str


class ArbiterErrorSignal(ArbiterSignal):
    """Emitted when an Arbiter encounters an error.

    Attributes:
        arbiter_role: The role label of the Arbiter.
        error: String representation of the error.
    """

    arbiter_role: str
    error: str


# ---------------------------------------------------------------------------
# Directive signals
# ---------------------------------------------------------------------------


class DirectiveSignal(Signal):
    """Base class for signals related to Directive lifecycle events."""


class DirectiveStartedSignal(DirectiveSignal):
    """Emitted when a Directive begins execution.

    Attributes:
        directive_description: The description of the Directive.
        arbiter_role: The role of the assigned Arbiter.
    """

    directive_description: str
    arbiter_role: str


class DirectiveCompletedSignal(DirectiveSignal):
    """Emitted when a Directive finishes successfully.

    Attributes:
        directive_description: The description of the Directive.
        output: The final output string.
    """

    directive_description: str
    output: str


class DirectiveErrorSignal(DirectiveSignal):
    """Emitted when a Directive fails with an error.

    Attributes:
        directive_description: The description of the Directive.
        error: String representation of the error.
    """

    directive_description: str
    error: str


# ---------------------------------------------------------------------------
# Conclave signals
# ---------------------------------------------------------------------------


class ConclaveSignal(Signal):
    """Base class for signals related to Conclave lifecycle events."""


class ConclaveStartedSignal(ConclaveSignal):
    """Emitted when a Conclave begins execution.

    Attributes:
        directive_count: Total number of Directives to execute.
        arbiter_count: Total number of Arbiters participating.
    """

    directive_count: int
    arbiter_count: int


class ConclaveCompletedSignal(ConclaveSignal):
    """Emitted when a Conclave finishes all Directives.

    Attributes:
        result_summary: Brief summary of the final output.
    """

    result_summary: str


class ConclaveErrorSignal(ConclaveSignal):
    """Emitted when a Conclave encounters a fatal error.

    Attributes:
        error: String representation of the error.
    """

    error: str


# ---------------------------------------------------------------------------
# Instrument signals
# ---------------------------------------------------------------------------


class InstrumentUsedSignal(Signal):
    """Emitted whenever an Instrument (tool) is invoked.

    Attributes:
        instrument_name: The registered name of the instrument.
        input_summary: Truncated summary of the input arguments.
        output_summary: Truncated summary of the output.
        cached: Whether the result was served from cache.
    """

    instrument_name: str
    input_summary: str
    output_summary: str
    cached: bool = False


# ---------------------------------------------------------------------------
# LLM signals
# ---------------------------------------------------------------------------


class LLMCallSignal(Signal):
    """Emitted for each LLM completion call.

    Attributes:
        model: The model identifier used.
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens in the completion.
    """

    model: str
    prompt_tokens: int
    completion_tokens: int


# ---------------------------------------------------------------------------
# Cascade signals
# ---------------------------------------------------------------------------


class CascadeSignal(Signal):
    """Base class for signals related to Cascade pipeline events."""


class CascadeStartedSignal(CascadeSignal):
    """Emitted when a Cascade pipeline method begins.

    Attributes:
        method_name: Fully-qualified method name that started.
    """

    method_name: str


class CascadeCompletedSignal(CascadeSignal):
    """Emitted when a Cascade pipeline method completes.

    Attributes:
        method_name: Fully-qualified method name that completed.
    """

    method_name: str
