"""Unified LLM provider interface for CodexConclave.

This module wraps `litellm` to provide a single, retrying, observable
interface to any LLM provider supported by litellm.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import litellm
from pydantic import BaseModel, ConfigDict

from codexconclave.llm.registry import (
    DEFAULT_MODEL,
    get_context_window,
)
from codexconclave.signals.bus import SignalBus
from codexconclave.signals.types import LLMCallSignal

logger = logging.getLogger(__name__)

# Suppress litellm's verbose default logging
litellm.suppress_debug_info = True


class LLMCallError(Exception):
    """Raised when all retry attempts to the LLM fail."""


class LLMProvider(BaseModel):
    """Unified interface to large language model providers.

    Wraps ``litellm.completion`` with retry logic, token counting,
    streaming support, and signal emission.

    Example::

        llm = LLMProvider(model="gpt-4o", temperature=0.5)
        response = llm.complete([{"role": "user", "content": "Hi!"}])
    """

    model: str = DEFAULT_MODEL
    """litellm-compatible model identifier."""

    temperature: float = 0.7
    """Sampling temperature (0.0 = deterministic, 1.0 = creative)."""

    max_tokens: int | None = None
    """Maximum tokens to generate.  ``None`` lets the model decide."""

    api_key: str | None = None
    """Provider API key.  Falls back to environment variables."""

    base_url: str | None = None
    """Custom base URL for self-hosted or proxied endpoints."""

    timeout: float = 600.0
    """Request timeout in seconds."""

    max_retries: int = 3
    """Number of retry attempts on transient failures."""

    streaming: bool = False
    """When ``True``, :meth:`complete` returns a generator."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ------------------------------------------------------------------
    # Public synchronous API
    # ------------------------------------------------------------------

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        response_format: type[BaseModel] | None = None,
    ) -> str | BaseModel:
        """Execute a completion request against the configured model.

        Retries up to :attr:`max_retries` times on transient errors.

        Args:
            messages: OpenAI-style message list.
            tools: Optional list of tool/function schemas for
                function-calling models.
            response_format: Optional Pydantic model class.  When
                provided, the response is parsed and validated into
                that model before returning.

        Returns:
            str | BaseModel: Text completion or structured model
                instance when ``response_format`` is set.

        Raises:
            LLMCallError: When all retry attempts are exhausted.
        """
        kwargs = self._build_kwargs(messages, tools=tools)

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                start = time.monotonic()
                response = litellm.completion(**kwargs)
                elapsed_ms = (time.monotonic() - start) * 1000

                usage = getattr(response, "usage", None)
                prompt_tokens = (
                    getattr(usage, "prompt_tokens", 0) if usage else 0
                )
                completion_tokens = (
                    getattr(usage, "completion_tokens", 0) if usage else 0
                )

                self._emit_llm_signal(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

                raw = response.choices[0].message.content or ""

                if response_format is not None:
                    return response_format.model_validate_json(raw)

                logger.debug(
                    "LLM call completed in %.1fms (attempt %d)",
                    elapsed_ms,
                    attempt,
                )
                return raw

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "LLM call attempt %d/%d failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(2 ** (attempt - 1))

        raise LLMCallError(
            f"All {self.max_retries} LLM call attempts failed."
        ) from last_error

    async def acomplete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> str:
        """Execute an asynchronous completion request.

        Args:
            messages: OpenAI-style message list.
            tools: Optional list of tool/function schemas.

        Returns:
            str: Text completion.

        Raises:
            LLMCallError: When all retry attempts are exhausted.
        """
        kwargs = self._build_kwargs(messages, tools=tools)

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await litellm.acompletion(**kwargs)

                usage = getattr(response, "usage", None)
                prompt_tokens = (
                    getattr(usage, "prompt_tokens", 0) if usage else 0
                )
                completion_tokens = (
                    getattr(usage, "completion_tokens", 0) if usage else 0
                )
                self._emit_llm_signal(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )

                return response.choices[0].message.content or ""

            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Async LLM call attempt %d/%d failed: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    import asyncio

                    await asyncio.sleep(2 ** (attempt - 1))

        raise LLMCallError(
            f"All {self.max_retries} async LLM call attempts failed."
        ) from last_error

    def stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        """Stream completion tokens from the model.

        Args:
            messages: OpenAI-style message list.

        Yields:
            str: Individual token strings as they arrive.

        Raises:
            LLMCallError: When the stream request fails.
        """
        kwargs = self._build_kwargs(messages)
        kwargs["stream"] = True

        try:
            response = litellm.completion(**kwargs)
            for chunk in response:
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except Exception as exc:
            raise LLMCallError(f"LLM stream request failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def context_window(self) -> int:
        """Return the context window size for the configured model.

        Returns:
            int: Number of tokens the model can process.
        """
        return get_context_window(self.model)

    # ------------------------------------------------------------------
    # Token counting
    # ------------------------------------------------------------------

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens in ``text`` for this model.

        Uses ``tiktoken`` when available; falls back to a word-count
        approximation otherwise.

        Args:
            text: The text to tokenize.

        Returns:
            int: Approximate or exact token count.
        """
        try:
            import tiktoken

            encoding_name = "cl100k_base"
            # Map known models to their encoding
            _model_encodings: dict[str, str] = {
                "gpt-4": "cl100k_base",
                "gpt-4o": "cl100k_base",
                "gpt-3.5-turbo": "cl100k_base",
            }
            encoding_name = _model_encodings.get(self.model, "cl100k_base")
            enc = tiktoken.get_encoding(encoding_name)
            return len(enc.encode(text))
        except Exception:
            # Rough fallback: ~4 chars per token
            return max(1, len(text) // 4)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_kwargs(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Construct the keyword arguments for a litellm call.

        Args:
            messages: Message list to include.
            tools: Optional tool schemas.

        Returns:
            dict[str, Any]: Keyword arguments for ``litellm.completion``.
        """
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "timeout": self.timeout,
        }
        if self.max_tokens is not None:
            kwargs["max_tokens"] = self.max_tokens
        if self.api_key is not None:
            kwargs["api_key"] = self.api_key
        if self.base_url is not None:
            kwargs["base_url"] = self.base_url
        if tools:
            kwargs["tools"] = tools
        return kwargs

    def _emit_llm_signal(
        self,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> None:
        """Emit an :class:`LLMCallSignal` to the active SignalBus.

        Args:
            prompt_tokens: Number of prompt tokens used.
            completion_tokens: Number of completion tokens generated.
        """
        try:
            bus = SignalBus.instance()
            bus.emit(
                LLMCallSignal(
                    model=self.model,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                )
            )
        except Exception:
            logger.debug("Failed to emit LLMCallSignal", exc_info=True)
