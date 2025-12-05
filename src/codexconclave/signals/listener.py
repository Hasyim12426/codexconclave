"""Abstract base class for signal listeners in CodexConclave."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import ClassVar

from codexconclave.signals.types import Signal

logger = logging.getLogger(__name__)


class BaseSignalListener(ABC):
    """Abstract base for objects that consume framework signals.

    Subclass this and override :meth:`handle` to react to signals.
    Set :attr:`signal_types` to restrict which signal types this
    listener will receive.  Leaving it empty means the listener
    accepts *all* signals.

    Example::

        class MyListener(BaseSignalListener):
            signal_types = (ArbiterStartedSignal,)

            def handle(self, signal: Signal) -> None:
                print(f"Arbiter started: {signal.arbiter_role}")
    """

    signal_types: ClassVar[tuple[type[Signal], ...]] = ()
    """Signal types this listener handles.

    An empty tuple means the listener accepts every signal type.
    """

    def accepts(self, signal: Signal) -> bool:
        """Return True if this listener should handle ``signal``.

        When :attr:`signal_types` is empty the listener accepts all
        signals.  Otherwise the signal must be an instance of one of
        the listed types.

        Args:
            signal: The incoming signal to test.

        Returns:
            bool: Whether this listener will process the signal.
        """
        if not self.signal_types:
            return True
        return isinstance(signal, self.signal_types)

    @abstractmethod
    def handle(self, signal: Signal) -> None:
        """Process the received signal.

        This method is called only when :meth:`accepts` returns
        ``True``.

        Args:
            signal: The signal to handle.
        """
