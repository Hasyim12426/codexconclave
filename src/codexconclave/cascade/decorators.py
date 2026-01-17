"""Decorators for defining Cascade (Flow) execution logic.

These decorators are applied to methods of a :class:`~codexconclave.cascade.pipeline.Cascade`
subclass to declare the execution graph without writing explicit
orchestration code.

Example::

    class MyPipeline(Cascade):
        state = MyState()

        @initiate
        def begin(self):
            return "hello"

        @observe(begin)
        def process(self, value: str):
            self.state.result = value.upper()

        @route
        def decide(self):
            if self.state.result == "HELLO":
                return self.handle_hello
            return self.handle_other
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

INITIATE_TAG: str = "__cascade_initiate__"
"""Attribute set on methods decorated with :func:`initiate`."""

OBSERVE_TAG: str = "__cascade_observe__"
"""Attribute set on methods decorated with :func:`observe`."""

ROUTE_TAG: str = "__cascade_route__"
"""Attribute set on methods decorated with :func:`route`."""

OBSERVE_TARGETS: str = "__cascade_observe_targets__"
"""Attribute holding the target method names/callables for :func:`observe`."""


def initiate(func: F) -> F:
    """Mark a method as a Cascade entry point.

    A Cascade may have multiple ``@initiate`` methods; they are all
    invoked when :meth:`~Cascade.execute` is called.

    Args:
        func: The method to mark as an entry point.

    Returns:
        F: The unmodified method with the initiate tag set.
    """
    setattr(func, INITIATE_TAG, True)
    return func


def observe(
    *targets: str | Callable[..., Any],
) -> Callable[[F], F]:
    """Mark a method to execute after specified methods complete.

    ``targets`` may be method references or method name strings.  The
    method will be called with the output of the triggering method as
    its first positional argument (when the signature allows it).

    Args:
        *targets: Method references or names to observe.

    Returns:
        Callable[[F], F]: Decorator that tags the method.

    Example::

        @observe(begin, "other_method")
        def after_start(self, value):
            ...
    """

    def decorator(func: F) -> F:
        setattr(func, OBSERVE_TAG, True)
        resolved: list[str] = []
        for t in targets:
            if callable(t):
                resolved.append(t.__name__)
            else:
                resolved.append(str(t))
        setattr(func, OBSERVE_TARGETS, tuple(resolved))
        return func

    return decorator


def route(func: F) -> F:
    """Mark a method as a conditional router.

    A router method should return either a callable (the next method
    to execute), a list of callables, or ``None`` to stop the branch.

    Args:
        func: The method to mark as a router.

    Returns:
        F: The unmodified method with the route tag set.
    """
    setattr(func, ROUTE_TAG, True)
    return func


def and_(
    *conditions: str | Callable[..., Any],
) -> tuple[str, tuple[str | Callable[..., Any], ...]]:
    """Declare that ALL listed methods must complete before triggering.

    Use as a target inside :func:`observe`::

        @observe(and_(method_a, method_b))
        def after_both(self):
            ...

    Args:
        *conditions: Method references or names.

    Returns:
        tuple: An ``("AND", conditions)`` sentinel tuple.
    """
    return ("AND", conditions)


def or_(
    *conditions: str | Callable[..., Any],
) -> tuple[str, tuple[str | Callable[..., Any], ...]]:
    """Declare that ANY of the listed methods completing triggers this.

    Use as a target inside :func:`observe`::

        @observe(or_(method_a, method_b))
        def after_either(self):
            ...

    Args:
        *conditions: Method references or names.

    Returns:
        tuple: An ``("OR", conditions)`` sentinel tuple.
    """
    return ("OR", conditions)
