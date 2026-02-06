# LLM Provider Configuration

CodexConclave uses [litellm](https://docs.litellm.ai) under the hood,
giving you access to every major LLM provider with a single interface.

---

## Quick Start

```python
from codexconclave.llm import LLMProvider

# OpenAI (default)
llm = LLMProvider(model="gpt-4o")

# Anthropic Claude
llm = LLMProvider(model="claude-3-5-sonnet-20241022")

# Google Gemini
llm = LLMProvider(model="gemini/gemini-1.5-pro")

# Groq (ultra-fast open-source models)
llm = LLMProvider(model="groq/llama-3.3-70b-versatile")
```

---

## Supported Providers

### OpenAI

```bash
export OPENAI_API_KEY=sk-...
```

| Model | Context Window |
|-------|---------------|
| `gpt-4o` | 128K tokens |
| `gpt-4o-mini` | 128K tokens |
| `gpt-4-turbo` | 128K tokens |
| `gpt-4` | 8K tokens |
| `gpt-3.5-turbo` | 16K tokens |
| `o1` | 200K tokens |
| `o1-mini` | 128K tokens |
| `o3-mini` | 200K tokens |

---

### Anthropic

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

| Model | Context Window |
|-------|---------------|
| `claude-3-5-sonnet-20241022` | 200K tokens |
| `claude-3-5-haiku-20241022` | 200K tokens |
| `claude-3-opus-20240229` | 200K tokens |
| `claude-3-sonnet-20240229` | 200K tokens |
| `claude-3-haiku-20240307` | 200K tokens |

---

### Google Gemini

```bash
export GOOGLE_API_KEY=...
```

| Model | Context Window |
|-------|---------------|
| `gemini/gemini-1.5-pro` | 2M tokens |
| `gemini/gemini-1.5-flash` | 1M tokens |
| `gemini/gemini-2.0-flash` | 1M tokens |

---

### AWS Bedrock

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
```

```python
llm = LLMProvider(
    model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
)
```

---

### Azure OpenAI

```bash
export AZURE_API_KEY=...
export AZURE_API_BASE=https://your-resource.openai.azure.com/
export AZURE_API_VERSION=2024-02-15-preview
```

```python
llm = LLMProvider(model="azure/gpt-4o")
```

---

### Groq

```bash
export GROQ_API_KEY=gsk_...
```

| Model | Context Window |
|-------|---------------|
| `groq/llama-3.3-70b-versatile` | 128K tokens |
| `groq/llama-3.1-70b-versatile` | 131K tokens |
| `groq/mixtral-8x7b-32768` | 32K tokens |

---

### Mistral

```bash
export MISTRAL_API_KEY=...
```

| Model | Context Window |
|-------|---------------|
| `mistral/mistral-large-latest` | 131K tokens |
| `mistral/mistral-medium-latest` | 131K tokens |

---

### DeepSeek

```bash
export DEEPSEEK_API_KEY=...
```

| Model | Context Window |
|-------|---------------|
| `deepseek/deepseek-chat` | 65K tokens |

---

## Advanced Configuration

```python
llm = LLMProvider(
    model="gpt-4o",
    temperature=0.2,          # lower = more deterministic
    max_tokens=2048,          # cap output length
    timeout=120.0,            # request timeout in seconds
    max_retries=5,            # retry on transient errors
    streaming=True,           # stream tokens as they arrive
    api_key="sk-...",         # override env var
    base_url="http://...",    # custom endpoint / proxy
)
```

---

## Token Counting

```python
token_count = llm.count_tokens("Hello, world!")
print(f"~{token_count} tokens")
```

Uses `tiktoken` when available; falls back to a character-based
approximation for models not in the tiktoken registry.

---

## Context Window

```python
print(f"Context window: {llm.context_window:,} tokens")
```

Looks up the model in the built-in registry. Returns 4,096 as
a conservative default for unrecognized models.

---

## Custom / Self-Hosted Models

Any OpenAI-compatible endpoint works:

```python
llm = LLMProvider(
    model="openai/my-fine-tuned-model",
    base_url="http://localhost:8000/v1",
    api_key="not-used",
)
```

For Ollama:

```python
llm = LLMProvider(
    model="ollama/llama3.2",
    base_url="http://localhost:11434",
)
```
