"""Context variable utilities for thread-safe CodexConclave state.

These context variables allow framework internals to determine the
currently-active Conclave, Arbiter, or Directive without passing
them explicitly through every call stack.

Each variable has three functions: ``get_*``, ``set_*``, and
``reset_*``.  Use the token returned by ``set_*`` to restore the
previous value via ``reset_*``.

Example::

    token = set_current_conclave(my_conclave)
    try:
        do_work()
    finally:
        reset_current_conclave(token)
"""

from __future__ import annotations

import contextvars
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Context variables
# ---------------------------------------------------------------------------

_current_conclave: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "current_conclave", default=None
)

_current_arbiter: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "current_arbiter", default=None
)

_current_directive: contextvars.ContextVar[Any | None] = (
    contextvars.ContextVar("current_directive", default=None)
)

# ---------------------------------------------------------------------------
# Conclave accessors
# ---------------------------------------------------------------------------


def get_current_conclave() -> Any | None:
    """Return the currently-active Conclave, or ``None``.

    Returns:
        Optional[Any]: The active Conclave instance.
    """
    return _current_conclave.get()


def set_current_conclave(conclave: Any) -> contextvars.Token[Any]:
    """Set the currently-active Conclave.

    Args:
        conclave: The Conclave instance to activate.

    Returns:
        contextvars.Token: Reset token for restoring the previous value.
    """
    return _current_conclave.set(conclave)


def reset_current_conclave(token: contextvars.Token[Any]) -> None:
    """Restore the Conclave context to its previous state.

    Args:
        token: The token returned by :func:`set_current_conclave`.
    """
    _current_conclave.reset(token)


# ---------------------------------------------------------------------------
# Arbiter accessors
# ---------------------------------------------------------------------------


def get_current_arbiter() -> Any | None:
    """Return the currently-active Arbiter, or ``None``.

    Returns:
        Optional[Any]: The active Arbiter instance.
    """
    return _current_arbiter.get()


def set_current_arbiter(arbiter: Any) -> contextvars.Token[Any]:
    """Set the currently-active Arbiter.

    Args:
        arbiter: The Arbiter instance to activate.

    Returns:
        contextvars.Token: Reset token for restoring the previous value.
    """
    return _current_arbiter.set(arbiter)


def reset_current_arbiter(token: contextvars.Token[Any]) -> None:
    """Restore the Arbiter context to its previous state.

    Args:
        token: The token returned by :func:`set_current_arbiter`.
    """
    _current_arbiter.reset(token)


# ---------------------------------------------------------------------------
# Directive accessors
# ---------------------------------------------------------------------------


def get_current_directive() -> Any | None:
    """Return the currently-active Directive, or ``None``.

    Returns:
        Optional[Any]: The active Directive instance.
    """
    return _current_directive.get()


def set_current_directive(directive: Any) -> contextvars.Token[Any]:
    """Set the currently-active Directive.

    Args:
        directive: The Directive instance to activate.

    Returns:
        contextvars.Token: Reset token for restoring the previous value.
    """
    return _current_directive.set(directive)


def reset_current_directive(token: contextvars.Token[Any]) -> None:
    """Restore the Directive context to its previous state.

    Args:
        token: The token returned by :func:`set_current_directive`.
    """
    _current_directive.reset(token)
