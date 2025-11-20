"""Unit tests for the LLM model registry."""

from __future__ import annotations

from codexconclave.llm.registry import (
    DEFAULT_CONTEXT_WINDOW,
    DEFAULT_MODEL,
    MODEL_REGISTRY,
    get_context_window,
)


class TestModelRegistry:
    """Tests for MODEL_REGISTRY contents and lookup."""

    def test_registry_is_dict(self) -> None:
        """MODEL_REGISTRY should be a dictionary."""
        assert isinstance(MODEL_REGISTRY, dict)

    def test_registry_has_entries(self) -> None:
        """Registry should have at least 20 model entries."""
        assert len(MODEL_REGISTRY) >= 20

    def test_gpt4o_present(self) -> None:
        """gpt-4o should be in the registry."""
        assert "gpt-4o" in MODEL_REGISTRY

    def test_gpt4o_context_window(self) -> None:
        """gpt-4o context window should be 128_000."""
        assert MODEL_REGISTRY["gpt-4o"] == 128_000

    def test_claude_sonnet_present(self) -> None:
        """A Claude 3.5 Sonnet model should be present."""
        assert "claude-3-5-sonnet-20241022" in MODEL_REGISTRY

    def test_claude_sonnet_context_window(self) -> None:
        """Claude Sonnet context window should be 200_000."""
        assert MODEL_REGISTRY["claude-3-5-sonnet-20241022"] == 200_000

    def test_gemini_pro_present(self) -> None:
        """A Gemini 1.5 Pro entry should be present."""
        assert "gemini/gemini-1.5-pro" in MODEL_REGISTRY

    def test_gemini_pro_large_context(self) -> None:
        """Gemini 1.5 Pro should have a very large context window."""
        assert MODEL_REGISTRY["gemini/gemini-1.5-pro"] >= 1_000_000

    def test_mistral_present(self) -> None:
        """A Mistral model should be in the registry."""
        assert "mistral/mistral-large-latest" in MODEL_REGISTRY

    def test_groq_present(self) -> None:
        """A Groq model should be in the registry."""
        assert "groq/llama-3.1-70b-versatile" in MODEL_REGISTRY

    def test_azure_gpt4o_present(self) -> None:
        """Azure GPT-4o should be in the registry."""
        assert "azure/gpt-4o" in MODEL_REGISTRY

    def test_bedrock_claude_present(self) -> None:
        """A Bedrock Claude model should be in the registry."""
        assert (
            "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
            in MODEL_REGISTRY
        )

    def test_all_values_are_positive_ints(self) -> None:
        """All context window values should be positive integers."""
        for model, window in MODEL_REGISTRY.items():
            assert isinstance(window, int), (
                f"{model} has non-int context window"
            )
            assert window > 0, f"{model} has non-positive context window"


class TestDefaultValues:
    """Tests for module-level defaults."""

    def test_default_model_is_string(self) -> None:
        """DEFAULT_MODEL should be a string."""
        assert isinstance(DEFAULT_MODEL, str)

    def test_default_model_is_gpt4o(self) -> None:
        """DEFAULT_MODEL should be 'gpt-4o'."""
        assert DEFAULT_MODEL == "gpt-4o"

    def test_default_context_window_positive(self) -> None:
        """DEFAULT_CONTEXT_WINDOW should be a positive integer."""
        assert isinstance(DEFAULT_CONTEXT_WINDOW, int)
        assert DEFAULT_CONTEXT_WINDOW > 0


class TestGetContextWindow:
    """Tests for the get_context_window helper function."""

    def test_known_model_returns_registry_value(self) -> None:
        """Known model returns its registry-defined context window."""
        assert get_context_window("gpt-4o") == 128_000

    def test_unknown_model_returns_default(self) -> None:
        """Unknown model falls back to DEFAULT_CONTEXT_WINDOW."""
        result = get_context_window("nonexistent/model-xyz")
        assert result == DEFAULT_CONTEXT_WINDOW

    def test_empty_string_returns_default(self) -> None:
        """Empty model string returns DEFAULT_CONTEXT_WINDOW."""
        assert get_context_window("") == DEFAULT_CONTEXT_WINDOW

    def test_o1_model(self) -> None:
        """o1 model should have 200_000 context."""
        assert get_context_window("o1") == 200_000

    def test_gpt4_8k(self) -> None:
        """gpt-4 base model should have 8_192 context."""
        assert get_context_window("gpt-4") == 8_192
