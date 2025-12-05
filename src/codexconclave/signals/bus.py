"""Central signal bus for CodexConclave event dispatching.

The :class:`SignalBus` is a thread-safe singleton that routes emitted
:class:`~codexconclave.signals.types.Signal` instances to all
registered :class:`~codexconclave.signals.listener.BaseSignalListener`
objects whose :meth:`~BaseSignalListener.accepts` method returns
``True``.
"""

from __future__ import annotations

import contextvars
import logging
import threading
from typing import Any, ClassVar

from codexconclave.signals.listener import BaseSignalListener
from codexconclave.signals.types import Signal

logger = logging.getLogger(__name__)

_bus_context: contextvars.ContextVar[SignalBus | None] = (
    contextvars.ContextVar("signal_bus", default=None)
)


class SignalBus:
    """Thread-safe singleton bus for dispatching framework signals.

    Usage::

        bus = SignalBus.instance()
        bus.register(my_listener)
        bus.emit(ConclaveStartedSignal(directive_count=3, arbiter_count=2))

    Listeners that raise exceptions are logged but do not interrupt
    signal delivery to remaining listeners.
    """

    _instance: ClassVar[SignalBus | None] = None
    _global_lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self) -> None:
        self._listeners: list[BaseSignalListener] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Singleton access
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> SignalBus:
        """Return the process-level singleton :class:`SignalBus`.

        The per-context bus is preferred when set via
        :func:`set_context_bus`.

        Returns:
            SignalBus: The active bus for the current context.
        """
        ctx_bus = _bus_context.get()
        if ctx_bus is not None:
            return ctx_bus

        if cls._instance is None:
            with cls._global_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Destroy the global singleton instance.

        Primarily useful in test teardown to ensure a clean slate.
        """
        with cls._global_lock:
            cls._instance = None

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------

    def register(self, listener: BaseSignalListener) -> None:
        """Add a listener to the bus.

        Args:
            listener: A :class:`BaseSignalListener` instance to
                register.  Duplicate registrations are silently
                ignored.
        """
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)
                logger.debug(
                    "Registered signal listener: %s",
                    type(listener).__name__,
                )

    def unregister(self, listener: BaseSignalListener) -> None:
        """Remove a previously registered listener.

        Args:
            listener: The listener to remove.  If it was never
                registered, this is a no-op.
        """
        with self._lock:
            try:
                self._listeners.remove(listener)
                logger.debug(
                    "Unregistered signal listener: %s",
                    type(listener).__name__,
                )
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    def emit(self, signal: Signal) -> None:
        """Dispatch ``signal`` to all accepting listeners.

        Listeners are called synchronously in registration order.
        Exceptions raised by individual listeners are caught, logged,
        and do not prevent delivery to subsequent listeners.

        Args:
            signal: The :class:`Signal` instance to dispatch.
        """
        with self._lock:
            snapshot = list(self._listeners)

        logger.debug(
            "Emitting %s from %s",
            type(signal).__name__,
            signal.source,
        )

        for listener in snapshot:
            if listener.accepts(signal):
                try:
                    listener.handle(signal)
                except Exception:
                    logger.exception(
                        "Listener %s raised an exception while handling %s",
                        type(listener).__name__,
                        type(signal).__name__,
                    )

    def listener_count(self) -> int:
        """Return the number of currently registered listeners.

        Returns:
            int: Count of registered listeners.
        """
        with self._lock:
            return len(self._listeners)


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------


def set_context_bus(bus: SignalBus) -> contextvars.Token[Any]:
    """Override the active bus for the current async/thread context.

    Args:
        bus: The :class:`SignalBus` to use in this context.

    Returns:
        contextvars.Token: Token that can be passed to
            :func:`reset_context_bus` to restore the previous value.
    """
    return _bus_context.set(bus)


def reset_context_bus(token: contextvars.Token[Any]) -> None:
    """Restore the bus context to its state before :func:`set_context_bus`.

    Args:
        token: The token returned by :func:`set_context_bus`.
    """
    _bus_context.reset(token)
