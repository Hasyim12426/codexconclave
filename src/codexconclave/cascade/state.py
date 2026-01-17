"""State management for Cascade pipelines.

Pipeline state is a Pydantic model that persists across method
invocations within a single :class:`~codexconclave.cascade.pipeline.Cascade`
execution.  Use :class:`CascadeState` for typed state and
:class:`UnstructuredCascadeState` for quick prototyping.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class CascadeState(BaseModel):
    """Base state class for Cascade pipelines.

    Subclass this to define strongly-typed state for your pipeline.

    Example::

        class MyState(CascadeState):
            query: str = ""
            result: Optional[str] = None
    """

    run_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for this pipeline run.",
    )

    model_config = {"arbitrary_types_allowed": True}


class UnstructuredCascadeState(CascadeState):
    """Flexible state backed by an arbitrary dictionary.

    Attribute access is proxied to :attr:`data`, making it easy to
    store ad-hoc values without defining a typed subclass.

    Example::

        state = UnstructuredCascadeState()
        state.answer = "42"
        print(state.answer)  # "42"
    """

    data: dict[str, Any] = Field(default_factory=dict)
    """Backing store for all dynamic attributes."""

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute reads to :attr:`data`.

        Args:
            name: Attribute name.

        Returns:
            Any: The stored value or ``None`` if not set.
        """
        if name.startswith("_") or name in self.model_fields:
            return super().__getattribute__(name)
        return self.data.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        """Proxy attribute writes to :attr:`data`.

        Args:
            name: Attribute name.
            value: Value to store.
        """
        if name.startswith("_") or name in self.model_fields:
            super().__setattr__(name, value)
        else:
            self.data[name] = value
