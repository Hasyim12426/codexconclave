# Contributing to CodexConclave

Thank you for your interest in contributing to CodexConclave. This document covers everything you need to get started — from setting up a development environment to submitting a pull request.

---

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Development Setup](#development-setup)
3. [Project Structure](#project-structure)
4. [Code Style](#code-style)
5. [Testing](#testing)
6. [Commit Messages](#commit-messages)
7. [Pull Request Process](#pull-request-process)
8. [Reporting Issues](#reporting-issues)
9. [Release Process](#release-process)

---

## Code of Conduct

By participating in this project you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

---

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- git

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/codexconclave/codexconclave.git
cd codexconclave

# Create a virtual environment and install all dev dependencies
uv venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate          # Windows

uv pip install -e ".[dev,memory,knowledge]"
```

### Using pip

```bash
git clone https://github.com/codexconclave/codexconclave.git
cd codexconclave

python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev,memory,knowledge]"
```

### Environment Variables

Copy the example environment file and fill in any API keys you need for integration testing:

```bash
cp .env.example .env
```

Disable OpenTelemetry during local development to avoid noise:

```bash
export OTEL_SDK_DISABLED=true
```

### Pre-commit Hooks

We use pre-commit to enforce style and linting automatically:

```bash
pre-commit install
```

This runs `ruff check`, `ruff format`, and `mypy` before every commit.

---

## Project Structure

```
codexconclave/
├── src/
│   └── codexconclave/
│       ├── __init__.py           # Public API surface
│       ├── conclave.py           # Conclave orchestrator
│       ├── directive.py          # Directive task model
│       ├── protocol.py           # Sequential / hierarchical enum
│       ├── arbiter/
│       │   ├── base.py           # ArbiterBase abstract class
│       │   └── core.py           # Arbiter implementation
│       ├── cascade/
│       │   ├── decorators.py     # @initiate, @observe, @route
│       │   ├── pipeline.py       # Cascade base class
│       │   └── state.py          # CascadeState models
│       ├── chronicle/            # Memory system
│       ├── cli/                  # CLI commands
│       ├── instruments/          # Tool system
│       ├── llm/                  # LLM provider abstraction
│       ├── observability/        # OpenTelemetry integration
│       ├── signals/              # SignalBus + typed events
│       └── utilities/            # Shared helpers
├── tests/                        # Pytest test suite
├── examples/                     # Runnable example projects
├── docs/                         # Supplementary documentation
├── pyproject.toml
├── README.md
└── CONTRIBUTING.md
```

---

## Code Style

### Ruff (linting + formatting)

All code is linted and formatted with [ruff](https://github.com/astral-sh/ruff):

```bash
# Check for lint errors
ruff check src/ tests/

# Auto-fix fixable issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/

# Check formatting without modifying files
ruff format --check src/ tests/
```

Key style rules enforced:
- Maximum line length: **79 characters** (E501 is ignored for docstrings)
- Import sorting (isort-compatible, via ruff `I` rules)
- Pyupgrade modernisation (Python 3.10+ idioms)
- Bugbear checks (common footguns)
- Simplification suggestions

### mypy (type checking)

All source code must pass strict mypy type checking:

```bash
mypy src/codexconclave/
```

Rules enforced:
- `strict = true` — all functions must have type annotations
- No implicit `Any`
- No untyped function definitions

### Docstrings

Use Google-style docstrings for all public classes and functions:

```python
def recall(self, query: str, limit: int = 5) -> list[ChronicleEntry]:
    """Retrieve relevant memories for a query.

    Args:
        query: The search query string.
        limit: Maximum number of entries to return.

    Returns:
        list[ChronicleEntry]: Matching entries sorted by relevance.

    Raises:
        ValueError: When query is empty.
    """
```

---

## Testing

### Running Tests

```bash
# Run full test suite
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_conclave.py

# Run a specific test
pytest tests/test_conclave.py::TestConclave::test_sequential_execution

# Run with coverage report
pytest --cov=src/codexconclave --cov-report=term-missing
```

### Coverage Requirements

All pull requests must maintain **at least 80% code coverage**. The CI pipeline enforces this with `--cov-fail-under=80`.

Check your coverage before opening a PR:

```bash
pytest --cov=src/codexconclave --cov-report=term-missing --cov-fail-under=80
```

### Writing Tests

- Place test files in `tests/` matching the source module name (e.g., `tests/test_conclave.py`)
- Use `pytest-mock` for mocking LLM calls and external services
- Use `pytest.mark.asyncio` for async tests
- Do not make real LLM API calls in unit tests — mock all `LLMProvider.complete()` calls
- Use `OTEL_SDK_DISABLED=true` in your test environment

Example test pattern:

```python
import pytest
from unittest.mock import MagicMock, patch
from codexconclave import Conclave, Arbiter, Directive, Protocol
from codexconclave.llm import LLMProvider


@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=LLMProvider)
    llm.complete.return_value = "Mocked LLM response"
    return llm


def test_sequential_conclave_returns_result(mock_llm):
    arbiter = Arbiter(
        role="Tester",
        objective="Test things",
        persona="A thorough tester",
        llm=mock_llm,
    )
    directive = Directive(
        description="Run a test",
        expected_output="Test passed",
        arbiter=arbiter,
    )
    conclave = Conclave(
        arbiters=[arbiter],
        directives=[directive],
        protocol=Protocol.sequential,
    )
    result = conclave.assemble()
    assert result.final_output is not None
```

---

## Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short summary>

[optional body]

[optional footer(s)]
```

### Types

| Type | When to use |
|------|-------------|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation changes only |
| `style` | Formatting changes (no logic change) |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `chore` | Build process, dependency updates, tooling |
| `perf` | Performance improvement |
| `ci` | CI/CD configuration changes |

### Examples

```
feat(arbiter): add support for custom system prompts

fix(cascade): handle None return values from @observe methods

docs(readme): update quick start example with cascade pipeline

test(chronicle): add tests for InMemoryChronicleStore expiry

chore(deps): bump litellm to 1.52.0
```

Breaking changes must include `BREAKING CHANGE:` in the footer or `!` after the type:

```
feat(llm)!: rename complete() to generate() for API clarity

BREAKING CHANGE: LLMProvider.complete() is now LLMProvider.generate()
```

---

## Pull Request Process

1. **Fork** the repository and create a branch from `main`:
   ```bash
   git checkout -b feat/my-new-feature
   ```

2. **Make your changes**, following the code style and testing requirements above.

3. **Run the full check suite** before pushing:
   ```bash
   ruff check src/ tests/
   ruff format --check src/ tests/
   mypy src/codexconclave/
   pytest --cov=src/codexconclave --cov-fail-under=80
   ```

4. **Push your branch** and open a pull request against `main`.

5. **Fill in the PR template** with:
   - A clear description of what changed and why
   - Links to any related issues
   - A testing plan

6. **Address review feedback** — a maintainer will review your PR and may request changes.

7. **Squash and merge** — PRs are merged via squash commit to keep the history clean.

### PR Checklist

- [ ] All tests pass
- [ ] Code coverage is at or above 80%
- [ ] New code has docstrings
- [ ] `ruff` and `mypy` pass with no errors
- [ ] CHANGELOG.md has an entry under `[Unreleased]`
- [ ] PR description explains the change

---

## Reporting Issues

Use the [GitHub issue tracker](https://github.com/codexconclave/codexconclave/issues) to report bugs or request features.

### Bug Reports

Please include:
- Python version (`python --version`)
- CodexConclave version (`pip show codexconclave`)
- Operating system
- Minimal reproducible example
- Full traceback

### Feature Requests

Open an issue with the `enhancement` label and describe:
- The use case driving the request
- The proposed API or behaviour
- Any alternatives you considered

---

## Release Process

Releases are managed by maintainers:

1. Update `CHANGELOG.md` — move entries from `[Unreleased]` to the new version section
2. Bump the version in `pyproject.toml` and `src/codexconclave/__init__.py`
3. Create a git tag: `git tag v1.x.y`
4. Push the tag: `git push origin v1.x.y`
5. The [publish workflow](.github/workflows/publish.yml) automatically builds and uploads to PyPI

---

Thank you for contributing to CodexConclave!
