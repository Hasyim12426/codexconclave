"""Abstract base class for Instruments (tools) in CodexConclave.

An Instrument is any callable capability exposed to Arbiters.  All
instruments must subclass :class:`BaseInstrument` and implement the
:meth:`execute` method.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, ConfigDict

from codexconclave.signals.bus import SignalBus
from codexconclave.signals.types import InstrumentUsedSignal

logger = logging.getLogger(__name__)


class InstrumentResult(BaseModel):
    """Captures the outcome of a single instrument invocation.

    Attributes:
        output: The string result returned by the instrument.
        cached: Whether the result was served from cache.
        execution_time_ms: Wall-clock time taken in milliseconds.
        instrument_name: Name of the instrument that produced this
            result.
    """

    output: str
    cached: bool = False
    execution_time_ms: float = 0.0
    instrument_name: str


class InstrumentValidationError(ValueError):
    """Raised when instrument inputs fail schema validation."""


class InstrumentExecutionError(RuntimeError):
    """Raised when an instrument encounters a runtime error."""


class BaseInstrument(BaseModel, ABC):
    """Abstract base for all instruments (tools) available to Arbiters.

    Subclass this and implement :meth:`execute`.  Optionally override
    :meth:`aexecute` for native async support.

    Example::

        class SearchInstrument(BaseInstrument):
            name = "web_search"
            description = "Search the web for information"

            def execute(self, query: str) -> str:
                return my_search_api(query)
    """

    name: str
    """Unique name used to identify this instrument in tool calls."""

    description: str
    """Human-readable description shown to the LLM."""

    cache_enabled: bool = False
    """When ``True``, repeated calls with the same inputs are cached."""

    cache_ttl: int = 3600
    """Cache time-to-live in seconds (only used when cache is enabled)."""

    max_uses: int | None = None
    """Hard limit on how many times this instrument may be invoked.
    ``None`` means unlimited."""

    result_as_answer: bool = False
    """When ``True``, the instrument result is used directly as the
    final Arbiter output without further LLM processing."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Internal state (excluded from Pydantic schema)
    _use_count: int = 0
    _cache: dict[str, tuple[str, float]] = {}

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """Execute the instrument with provided arguments.

        Args:
            **kwargs: Keyword arguments as defined by the instrument's
                parameter contract.

        Returns:
            str: The result of the instrument execution.

        Raises:
            InstrumentExecutionError: On runtime failure.
        """

    # ------------------------------------------------------------------
    # Public execution entry point
    # ------------------------------------------------------------------

    def run(self, **kwargs: Any) -> InstrumentResult:
        """Execute the instrument with caching, use-count, and signals.

        This is the preferred entry point over calling :meth:`execute`
        directly.

        Args:
            **kwargs: Arguments forwarded to :meth:`execute`.

        Returns:
            InstrumentResult: Wrapped result including metadata.

        Raises:
            InstrumentExecutionError: When max_uses is exceeded or
                execution fails.
        """
        self._validate_use_limit()

        cache_key = self._make_cache_key(kwargs)
        cached_result = self._get_cached(cache_key)
        if cached_result is not None:
            logger.debug("Cache hit for instrument '%s'", self.name)
            self._emit_signal(
                input_summary=str(kwargs)[:200],
                output_summary=cached_result[:200],
                cached=True,
            )
            return InstrumentResult(
                output=cached_result,
                cached=True,
                execution_time_ms=0.0,
                instrument_name=self.name,
            )

        self._validate_inputs(**kwargs)

        start = time.monotonic()
        try:
            output = self.execute(**kwargs)
        except InstrumentExecutionError:
            raise
        except Exception as exc:
            raise InstrumentExecutionError(
                f"Instrument '{self.name}' failed: {exc}"
            ) from exc
        elapsed_ms = (time.monotonic() - start) * 1000

        self._use_count += 1
        self._set_cached(cache_key, output)

        self._emit_signal(
            input_summary=str(kwargs)[:200],
            output_summary=output[:200],
            cached=False,
        )

        return InstrumentResult(
            output=output,
            cached=False,
            execution_time_ms=elapsed_ms,
            instrument_name=self.name,
        )

    async def aexecute(self, **kwargs: Any) -> str:
        """Async execution — wraps the synchronous :meth:`execute`.

        Override in subclasses for native async support.

        Args:
            **kwargs: Arguments forwarded to :meth:`execute`.

        Returns:
            str: The result string.
        """
        return self.execute(**kwargs)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def to_tool_schema(self) -> dict[str, Any]:
        """Return an OpenAI-compatible function/tool schema.

        Returns:
            dict[str, Any]: JSON schema describing this instrument's
                callable interface.
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self._parameters_schema(),
            },
        }

    def _parameters_schema(self) -> dict[str, Any]:
        """Build a generic parameters schema.

        Subclasses should override this to provide a precise schema.

        Returns:
            dict[str, Any]: JSON Schema object for parameters.
        """
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_inputs(self, **kwargs: Any) -> None:
        """Validate inputs before execution.

        Subclasses may override to add domain-specific validation.

        Args:
            **kwargs: The inputs to validate.

        Raises:
            InstrumentValidationError: On invalid inputs.
        """
        # Default: no validation; subclasses override as needed

    def _validate_use_limit(self) -> None:
        """Check if the use limit has been reached.

        Raises:
            InstrumentExecutionError: When :attr:`max_uses` is set and
                the instrument has been used that many times.
        """
        if self.max_uses is not None and self._use_count >= self.max_uses:
            raise InstrumentExecutionError(
                f"Instrument '{self.name}' has reached its maximum "
                f"use limit of {self.max_uses}."
            )

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _make_cache_key(self, kwargs: dict[str, Any]) -> str:
        """Produce a deterministic cache key from ``kwargs``.

        Args:
            kwargs: The input keyword arguments.

        Returns:
            str: SHA-256 hex digest of the serialized inputs.
        """
        raw = json.dumps(kwargs, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _get_cached(self, key: str) -> str | None:
        """Retrieve a cached result if still valid.

        Args:
            key: The cache key to look up.

        Returns:
            Optional[str]: Cached output or ``None`` if not found or
                expired.
        """
        if not self.cache_enabled:
            return None
        entry = self._cache.get(key)
        if entry is None:
            return None
        value, stored_at = entry
        if time.monotonic() - stored_at > self.cache_ttl:
            del self._cache[key]
            return None
        return value

    def _set_cached(self, key: str, value: str) -> None:
        """Store a result in the cache.

        Args:
            key: The cache key.
            value: The result to cache.
        """
        if self.cache_enabled:
            self._cache[key] = (value, time.monotonic())

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _emit_signal(
        self,
        input_summary: str,
        output_summary: str,
        cached: bool,
    ) -> None:
        """Emit an :class:`InstrumentUsedSignal` to the bus.

        Args:
            input_summary: Brief description of the inputs.
            output_summary: Brief description of the output.
            cached: Whether the result came from cache.
        """
        try:
            SignalBus.instance().emit(
                InstrumentUsedSignal(
                    instrument_name=self.name,
                    input_summary=input_summary,
                    output_summary=output_summary,
                    cached=cached,
                )
            )
        except Exception:
            logger.debug("Failed to emit InstrumentUsedSignal", exc_info=True)
