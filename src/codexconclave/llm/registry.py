"""Model registry mapping model identifiers to context window sizes.

Add or override entries at runtime::

    from codexconclave.llm.registry import MODEL_REGISTRY
    MODEL_REGISTRY["my-provider/my-model"] = 32_768
"""

from __future__ import annotations

MODEL_REGISTRY: dict[str, int] = {
    # ------------------------------------------------------------------
    # OpenAI
    # ------------------------------------------------------------------
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4-turbo-preview": 128_000,
    "gpt-4": 8_192,
    "gpt-4-32k": 32_768,
    "gpt-3.5-turbo": 16_385,
    "gpt-3.5-turbo-16k": 16_385,
    "o1": 200_000,
    "o1-mini": 128_000,
    "o1-preview": 128_000,
    "o3-mini": 200_000,
    # ------------------------------------------------------------------
    # Anthropic
    # ------------------------------------------------------------------
    "claude-3-5-sonnet-20241022": 200_000,
    "claude-3-5-haiku-20241022": 200_000,
    "claude-3-opus-20240229": 200_000,
    "claude-3-sonnet-20240229": 200_000,
    "claude-3-haiku-20240307": 200_000,
    "claude-2.1": 200_000,
    "claude-2.0": 100_000,
    "claude-instant-1.2": 100_000,
    # ------------------------------------------------------------------
    # Google
    # ------------------------------------------------------------------
    "gemini/gemini-1.5-pro": 2_000_000,
    "gemini/gemini-1.5-flash": 1_000_000,
    "gemini/gemini-2.0-flash": 1_000_000,
    "gemini/gemini-1.0-pro": 32_760,
    "gemini/gemini-ultra": 32_760,
    # ------------------------------------------------------------------
    # Mistral
    # ------------------------------------------------------------------
    "mistral/mistral-large-latest": 131_072,
    "mistral/mistral-medium-latest": 131_072,
    "mistral/mistral-small-latest": 131_072,
    "mistral/open-mistral-7b": 32_768,
    "mistral/open-mixtral-8x7b": 32_768,
    "mistral/open-mixtral-8x22b": 65_536,
    # ------------------------------------------------------------------
    # Groq
    # ------------------------------------------------------------------
    "groq/llama-3.1-70b-versatile": 131_072,
    "groq/llama-3.1-8b-instant": 131_072,
    "groq/llama-3.2-90b-text-preview": 131_072,
    "groq/mixtral-8x7b-32768": 32_768,
    "groq/gemma-7b-it": 8_192,
    "groq/gemma2-9b-it": 8_192,
    # ------------------------------------------------------------------
    # DeepSeek
    # ------------------------------------------------------------------
    "deepseek/deepseek-chat": 65_536,
    "deepseek/deepseek-coder": 65_536,
    # ------------------------------------------------------------------
    # Cohere
    # ------------------------------------------------------------------
    "cohere/command-r": 128_000,
    "cohere/command-r-plus": 128_000,
    "cohere/command": 4_096,
    # ------------------------------------------------------------------
    # AWS Bedrock
    # ------------------------------------------------------------------
    "bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0": 200_000,
    "bedrock/anthropic.claude-3-opus-20240229-v1:0": 200_000,
    "bedrock/anthropic.claude-3-haiku-20240307-v1:0": 200_000,
    "bedrock/amazon.titan-text-express-v1": 8_192,
    "bedrock/meta.llama3-70b-instruct-v1:0": 8_192,
    # ------------------------------------------------------------------
    # Azure OpenAI
    # ------------------------------------------------------------------
    "azure/gpt-4o": 128_000,
    "azure/gpt-4o-mini": 128_000,
    "azure/gpt-4": 8_192,
    "azure/gpt-4-32k": 32_768,
    "azure/gpt-3.5-turbo": 16_385,
    # ------------------------------------------------------------------
    # Together AI
    # ------------------------------------------------------------------
    "together_ai/meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": 131_072,
    "together_ai/mistralai/Mixtral-8x22B-Instruct-v0.1": 65_536,
    # ------------------------------------------------------------------
    # Fireworks AI
    # ------------------------------------------------------------------
    "fireworks_ai/accounts/fireworks/models/llama-v3p1-70b-instruct": 131_072,
    "fireworks_ai/accounts/fireworks/models/mixtral-8x22b-instruct": 65_536,
}
"""Registry of known model identifiers and their context window sizes.

Keys follow the ``provider/model-name`` convention used by litellm.
OpenAI models omit the provider prefix.
"""

DEFAULT_CONTEXT_WINDOW: int = 4_096
"""Fallback context window used when a model is not in the registry."""

DEFAULT_MODEL: str = "gpt-4o"
"""Default model identifier used by :class:`~codexconclave.llm.provider.LLMProvider`."""


def get_context_window(model: str) -> int:
    """Look up the context window size for ``model``.

    Falls back to :data:`DEFAULT_CONTEXT_WINDOW` when the model is
    unknown.

    Args:
        model: A litellm-compatible model identifier.

    Returns:
        int: Context window size in tokens.
    """
    return MODEL_REGISTRY.get(model, DEFAULT_CONTEXT_WINDOW)
