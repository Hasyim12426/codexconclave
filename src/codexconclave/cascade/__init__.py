"""Cascade subsystem — event-driven pipeline orchestration."""

from codexconclave.cascade.decorators import (
    and_,
    initiate,
    observe,
    or_,
    route,
)
from codexconclave.cascade.pipeline import Cascade, CascadeResult
from codexconclave.cascade.state import (
    CascadeState,
    UnstructuredCascadeState,
)

__all__ = [
    "Cascade",
    "CascadeResult",
    "CascadeState",
    "UnstructuredCascadeState",
    "initiate",
    "observe",
    "route",
    "and_",
    "or_",
]
