"""Execution protocol definitions for Conclave orchestration."""

from enum import Enum


class Protocol(str, Enum):
    """Defines the execution strategy for a Conclave.

    Choose a protocol based on your workflow requirements:
    - Use ``sequential`` for linear pipelines where order matters.
    - Use ``hierarchical`` when a manager should delegate and
      validate work among multiple Arbiters.
    """

    sequential = "sequential"
    """Directives execute one after another, each receiving prior
    outputs as context."""

    hierarchical = "hierarchical"
    """A manager Arbiter coordinates other Arbiters, delegating
    and validating work."""

    def __str__(self) -> str:
        """Return the plain string value (e.g. ``"sequential"``)."""
        return self.value
