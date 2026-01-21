"""Observability tracker using OpenTelemetry for CodexConclave.

Tracks anonymised framework usage metrics to help improve the
framework.  Set ``OTEL_SDK_DISABLED=true`` (or ``1``) to opt out.
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_OTEL_AVAILABLE = False
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    pass


class ObservabilityTracker:
    """Tracks usage metrics via OpenTelemetry for framework improvement.

    All data is anonymised — no user inputs or outputs are ever
    transmitted.  Only structural metadata such as model name,
    directive counts, and execution times are recorded.

    Disable by setting the environment variable
    ``OTEL_SDK_DISABLED=true`` or ``OTEL_SDK_DISABLED=1``.
    """

    OTLP_ENDPOINT: str = "https://telemetry.codexconclave.ai/v1/traces"
    """Default OTLP HTTP endpoint for span export."""

    SERVICE_NAME: str = "codexconclave"

    def __init__(self) -> None:
        """Initialise the tracker and conditionally set up OpenTelemetry."""
        disabled_env = os.getenv("OTEL_SDK_DISABLED", "").lower()
        self._enabled = disabled_env not in ("true", "1")
        self._tracer: Any | None = None

        if self._enabled and _OTEL_AVAILABLE:
            self._tracer = self._setup_tracer()
        elif self._enabled and not _OTEL_AVAILABLE:
            logger.debug(
                "OpenTelemetry packages not available; "
                "observability is disabled."
            )
            self._enabled = False

    # ------------------------------------------------------------------
    # Tracer setup
    # ------------------------------------------------------------------

    def _setup_tracer(self) -> Any | None:
        """Initialise and return an OpenTelemetry tracer.

        Returns:
            Optional[Any]: Configured tracer or ``None`` on failure.
        """
        if not _OTEL_AVAILABLE:
            return None

        try:
            resource = Resource.create({"service.name": self.SERVICE_NAME})
            provider = TracerProvider(resource=resource)

            exporter = OTLPSpanExporter(
                endpoint=self.OTLP_ENDPOINT,
                timeout=5,
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))

            trace.set_tracer_provider(provider)
            tracer = trace.get_tracer(self.SERVICE_NAME)
            logger.debug("ObservabilityTracker: tracer initialised.")
            return tracer

        except Exception as exc:
            logger.debug(
                "ObservabilityTracker: failed to set up tracer: %s",
                exc,
            )
            self._enabled = False
            return None

    # ------------------------------------------------------------------
    # Recording methods
    # ------------------------------------------------------------------

    def record_conclave_execution(
        self,
        arbiter_count: int,
        directive_count: int,
        protocol: str,
        model: str,
    ) -> None:
        """Record the start of a Conclave execution.

        Args:
            arbiter_count: Number of Arbiters in the Conclave.
            directive_count: Number of Directives to execute.
            protocol: The execution protocol name.
            model: The primary LLM model identifier.
        """
        if not self._enabled or self._tracer is None:
            return
        try:
            with self._tracer.start_as_current_span(
                "conclave.execution"
            ) as span:
                span.set_attribute("arbiter_count", arbiter_count)
                span.set_attribute("directive_count", directive_count)
                span.set_attribute("protocol", protocol)
                span.set_attribute("model", model)
        except Exception as exc:
            logger.debug(
                "ObservabilityTracker: record_conclave_execution failed: %s",
                exc,
            )

    def record_instrument_usage(
        self,
        instrument_name: str,
        execution_time_ms: float,
    ) -> None:
        """Record an instrument invocation.

        Args:
            instrument_name: The name of the instrument.
            execution_time_ms: Execution time in milliseconds.
        """
        if not self._enabled or self._tracer is None:
            return
        try:
            with self._tracer.start_as_current_span(
                "instrument.usage"
            ) as span:
                span.set_attribute("instrument_name", instrument_name)
                span.set_attribute("execution_time_ms", execution_time_ms)
        except Exception as exc:
            logger.debug(
                "ObservabilityTracker: record_instrument_usage failed: %s",
                exc,
            )

    def record_llm_call(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Record a single LLM completion call.

        Args:
            model: The model identifier used.
            prompt_tokens: Tokens in the prompt.
            completion_tokens: Tokens in the completion.
        """
        if not self._enabled or self._tracer is None:
            return
        try:
            with self._tracer.start_as_current_span("llm.call") as span:
                span.set_attribute("model", model)
                span.set_attribute("prompt_tokens", prompt_tokens)
                span.set_attribute("completion_tokens", completion_tokens)
                span.set_attribute(
                    "total_tokens",
                    prompt_tokens + completion_tokens,
                )
        except Exception as exc:
            logger.debug(
                "ObservabilityTracker: record_llm_call failed: %s",
                exc,
            )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Return whether telemetry is currently active.

        Returns:
            bool: ``True`` if observability is enabled and functional.
        """
        return self._enabled
