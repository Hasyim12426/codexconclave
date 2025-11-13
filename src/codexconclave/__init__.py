"""CodexConclave — a production-grade framework for orchestrating
autonomous AI agent teams.

This package provides two complementary execution models:

1. **Conclave** (agent-based autonomy) — teams of
   :class:`~codexconclave.arbiter.core.Arbiter` instances working on
   :class:`~codexconclave.directive.Directive` units.

2. **Cascade** (event-driven control) — precise workflow pipelines
   built with :func:`~codexconclave.cascade.decorators.initiate`,
   :func:`~codexconclave.cascade.decorators.observe`, and
   :func:`~codexconclave.cascade.decorators.route` decorators.

Quick-start::

    from codexconclave import Arbiter, Conclave, Directive, Protocol
    from codexconclave.llm import LLMProvider

    llm = LLMProvider(model="gpt-4o")

    researcher = Arbiter(
        role="Researcher",
        objective="Research AI topics thoroughly.",
        llm=llm,
    )

    task = Directive(
        description="Explain transformer architectures.",
        expected_output="A clear technical explanation.",
        arbiter=researcher,
    )

    conclave = Conclave(
        arbiters=[researcher],
        directives=[task],
    )

    result = conclave.assemble()
    print(result)
"""

from codexconclave.arbiter.core import Arbiter, ArbiterResult
from codexconclave.cascade.pipeline import Cascade, CascadeResult
from codexconclave.chronicle.memory import Chronicle
from codexconclave.conclave import Conclave, ConclaveResult
from codexconclave.directive import Directive, DirectiveResult
from codexconclave.instruments.base import BaseInstrument
from codexconclave.llm.provider import LLMProvider
from codexconclave.protocol import Protocol

__all__ = [
    # Core execution
    "Conclave",
    "ConclaveResult",
    "Arbiter",
    "ArbiterResult",
    "Directive",
    "DirectiveResult",
    "Protocol",
    # Flow / pipeline
    "Cascade",
    "CascadeResult",
    # Instruments
    "BaseInstrument",
    # LLM
    "LLMProvider",
    # Memory
    "Chronicle",
]

__version__ = "1.0.0"
