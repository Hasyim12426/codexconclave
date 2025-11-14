"""Shared test fixtures for the CodexConclave test suite."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_llm() -> MagicMock:
    """Return a mock LLMProvider that returns predictable responses.

    Returns:
        MagicMock: A configured mock with sensible defaults.
    """
    llm = MagicMock()
    llm.complete.return_value = "Mocked LLM response"
    llm.model = "gpt-4o"
    llm.context_window = 128_000
    llm.count_tokens.return_value = 10
    return llm


@pytest.fixture
def sample_arbiter(mock_llm: MagicMock):
    """Return a fully-configured sample Arbiter.

    Args:
        mock_llm: Injected mock LLM fixture.

    Returns:
        Arbiter: A configured test Arbiter.
    """
    from codexconclave import Arbiter

    return Arbiter(
        role="Research Analyst",
        objective="Analyse data and provide insights",
        persona="Expert data analyst with 10 years experience",
        llm=mock_llm,
    )


@pytest.fixture
def sample_directive():
    """Return a sample Directive for testing.

    Returns:
        Directive: A configured test Directive.
    """
    from codexconclave import Directive

    return Directive(
        description="Research the history of artificial intelligence",
        expected_output="A comprehensive summary of AI history",
    )


@pytest.fixture
def sample_conclave(sample_arbiter, sample_directive):
    """Return a sample Conclave wired with the fixture Arbiter and Directive.

    Args:
        sample_arbiter: Injected Arbiter fixture.
        sample_directive: Injected Directive fixture.

    Returns:
        Conclave: A configured test Conclave.
    """
    from codexconclave import Conclave, Protocol

    sample_directive.arbiter = sample_arbiter
    return Conclave(
        arbiters=[sample_arbiter],
        directives=[sample_directive],
        protocol=Protocol.sequential,
    )
