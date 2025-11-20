"""Unit tests for LLMProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from codexconclave.llm.provider import LLMCallError, LLMProvider
from codexconclave.llm.registry import DEFAULT_MODEL


class TestLLMProviderDefaults:
    """Tests for LLMProvider default values."""

    def test_default_model(self) -> None:
        """Default model should be DEFAULT_MODEL."""
        llm = LLMProvider()
        assert llm.model == DEFAULT_MODEL

    def test_default_temperature(self) -> None:
        """Default temperature should be 0.7."""
        assert LLMProvider().temperature == 0.7

    def test_default_max_tokens_none(self) -> None:
        """Default max_tokens should be None."""
        assert LLMProvider().max_tokens is None

    def test_default_timeout(self) -> None:
        """Default timeout should be 600.0."""
        assert LLMProvider().timeout == 600.0

    def test_default_max_retries(self) -> None:
        """Default max_retries should be 3."""
        assert LLMProvider().max_retries == 3

    def test_default_streaming_false(self) -> None:
        """Streaming should be disabled by default."""
        assert LLMProvider().streaming is False

    def test_context_window_property(self) -> None:
        """context_window property should reflect registry value."""
        llm = LLMProvider(model="gpt-4o")
        assert llm.context_window == 128_000

    def test_context_window_unknown_model(self) -> None:
        """Unknown model context_window should fall back to default."""
        from codexconclave.llm.registry import DEFAULT_CONTEXT_WINDOW

        llm = LLMProvider(model="unknown-model")
        assert llm.context_window == DEFAULT_CONTEXT_WINDOW


class TestLLMProviderComplete:
    """Tests for the synchronous complete() method."""

    def _mock_litellm_response(
        self, content: str, prompt: int = 10, completion: int = 5
    ) -> MagicMock:
        """Build a mock litellm response object."""
        usage = MagicMock()
        usage.prompt_tokens = prompt
        usage.completion_tokens = completion

        choice = MagicMock()
        choice.message.content = content

        resp = MagicMock()
        resp.choices = [choice]
        resp.usage = usage
        return resp

    @patch("codexconclave.llm.provider.litellm.completion")
    def test_complete_returns_text(self, mock_completion: MagicMock) -> None:
        """complete() should return the response text."""
        mock_completion.return_value = self._mock_litellm_response("Hello!")
        llm = LLMProvider(model="gpt-4o")
        result = llm.complete([{"role": "user", "content": "Hi"}])
        assert result == "Hello!"

    @patch("codexconclave.llm.provider.litellm.completion")
    def test_complete_passes_model(self, mock_completion: MagicMock) -> None:
        """complete() should pass the configured model to litellm."""
        mock_completion.return_value = self._mock_litellm_response("ok")
        llm = LLMProvider(model="gpt-4o-mini")
        llm.complete([{"role": "user", "content": "test"}])

        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"

    @patch("codexconclave.llm.provider.litellm.completion")
    def test_complete_passes_tools(self, mock_completion: MagicMock) -> None:
        """complete() should forward tools to litellm when provided."""
        mock_completion.return_value = self._mock_litellm_response("ok")
        llm = LLMProvider()
        tools = [{"type": "function", "function": {"name": "test"}}]
        llm.complete([{"role": "user", "content": "test"}], tools=tools)
        call_kwargs = mock_completion.call_args[1]
        assert call_kwargs["tools"] == tools

    @patch(
        "codexconclave.llm.provider.litellm.completion",
        side_effect=RuntimeError("API error"),
    )
    def test_complete_retries_on_failure(
        self, mock_completion: MagicMock
    ) -> None:
        """complete() should retry max_retries times before raising."""
        llm = LLMProvider(max_retries=2)
        with pytest.raises(LLMCallError):
            llm.complete([{"role": "user", "content": "hi"}])
        assert mock_completion.call_count == 2

    @patch("codexconclave.llm.provider.litellm.completion")
    def test_complete_structured_output(
        self, mock_completion: MagicMock
    ) -> None:
        """complete() with response_format should parse JSON output."""
        from pydantic import BaseModel as PydanticModel

        class MySchema(PydanticModel):
            answer: str

        mock_completion.return_value = self._mock_litellm_response(
            '{"answer": "42"}'
        )
        llm = LLMProvider()
        result = llm.complete(
            [{"role": "user", "content": "what is 6x7"}],
            response_format=MySchema,
        )
        assert isinstance(result, MySchema)
        assert result.answer == "42"


class TestLLMProviderStream:
    """Tests for the stream() method."""

    @patch("codexconclave.llm.provider.litellm.completion")
    def test_stream_yields_tokens(self, mock_completion: MagicMock) -> None:
        """stream() should yield individual token strings."""
        chunks = []
        for token in ("Hello", " world", "!"):
            chunk = MagicMock()
            chunk.choices[0].delta.content = token
            chunks.append(chunk)

        mock_completion.return_value = iter(chunks)

        llm = LLMProvider()
        tokens = list(llm.stream([{"role": "user", "content": "hi"}]))
        assert tokens == ["Hello", " world", "!"]

    @patch(
        "codexconclave.llm.provider.litellm.completion",
        side_effect=RuntimeError("stream error"),
    )
    def test_stream_raises_llm_call_error(self, _: MagicMock) -> None:
        """stream() should raise LLMCallError on failure."""
        llm = LLMProvider()
        with pytest.raises(LLMCallError):
            list(llm.stream([{"role": "user", "content": "hi"}]))


class TestLLMProviderTokenCount:
    """Tests for the count_tokens() method."""

    def test_count_tokens_returns_positive_int(self) -> None:
        """count_tokens should return a positive integer."""
        llm = LLMProvider()
        # Patch tiktoken to avoid import dependency in tests
        with patch("codexconclave.llm.provider.litellm"):
            count = llm.count_tokens("Hello world this is a test.")
            assert isinstance(count, int)
            assert count > 0

    def test_count_tokens_fallback_without_tiktoken(self) -> None:
        """count_tokens falls back gracefully when tiktoken fails."""
        llm = LLMProvider()
        with patch(
            "builtins.__import__",
            side_effect=ImportError("tiktoken not found"),
        ):
            # Direct fallback: ~4 chars per token
            count = llm.count_tokens("Hello world")
            assert count >= 1
