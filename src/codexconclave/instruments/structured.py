"""StructuredInstrument — wraps a Python callable as an Instrument.

Use :meth:`StructuredInstrument.from_function` to create an instrument
from any function, preserving its docstring and type annotations.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from codexconclave.instruments.base import (
    BaseInstrument,
    InstrumentValidationError,
)

logger = logging.getLogger(__name__)


class StructuredInstrument(BaseInstrument):
    """Wraps a callable function as a first-class Instrument.

    The wrapped function's signature drives the instrument's schema,
    enabling automatic input validation and LLM tool-calling
    compatibility.

    Example::

        def add(a: int, b: int) -> str:
            \"\"\"Add two numbers and return the result.\"\"\"
            return str(a + b)

        instrument = StructuredInstrument.from_function(add)
        result = instrument.run(a=3, b=4)
        # result.output == "7"
    """

    func: Callable[..., str]
    """The underlying callable to invoke."""

    args_schema: type[BaseModel] | None = None
    """Optional Pydantic model for strict input validation."""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_function(
        cls,
        func: Callable[..., str],
        name: str | None = None,
        description: str | None = None,
    ) -> StructuredInstrument:
        """Create a :class:`StructuredInstrument` from a Python function.

        The function's ``__name__`` and ``__doc__`` are used as the
        default ``name`` and ``description`` respectively.

        Args:
            func: The callable to wrap.
            name: Override for the instrument name.
            description: Override for the instrument description.

        Returns:
            StructuredInstrument: A ready-to-use instrument.

        Raises:
            ValueError: When no description can be inferred.
        """
        resolved_name = name or func.__name__
        resolved_desc = (
            description
            or inspect.getdoc(func)
            or f"Execute the {resolved_name} function."
        )

        return cls(
            name=resolved_name,
            description=resolved_desc,
            func=func,
        )

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, **kwargs: Any) -> str:
        """Invoke the wrapped function with ``kwargs``.

        When :attr:`args_schema` is set, inputs are first validated
        through that model before calling the function.

        Args:
            **kwargs: Arguments to pass to the wrapped callable.

        Returns:
            str: The function's return value converted to string.

        Raises:
            InstrumentValidationError: On Pydantic validation failure.
        """
        if self.args_schema is not None:
            try:
                validated = self.args_schema(**kwargs)
                # Pass validated fields back as kwargs
                kwargs = validated.model_dump()
            except Exception as exc:
                raise InstrumentValidationError(
                    f"Input validation failed for '{self.name}': {exc}"
                ) from exc

        result = self.func(**kwargs)

        if not isinstance(result, str):
            result = str(result)
        return result

    # ------------------------------------------------------------------
    # Schema generation
    # ------------------------------------------------------------------

    def _parameters_schema(self) -> dict[str, Any]:
        """Build a JSON Schema from the wrapped function's signature.

        When :attr:`args_schema` is set, its Pydantic JSON schema is
        used.  Otherwise, the function's type annotations are
        introspected to produce a best-effort schema.

        Returns:
            dict[str, Any]: JSON Schema object.
        """
        if self.args_schema is not None:
            schema = self.args_schema.model_json_schema()
            return {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            }

        return self._schema_from_signature()

    def _schema_from_signature(self) -> dict[str, Any]:
        """Infer a JSON Schema from the function's parameter annotations.

        Uses ``typing.get_type_hints()`` to resolve string annotations
        produced by ``from __future__ import annotations``.

        Returns:
            dict[str, Any]: Best-effort JSON Schema for the function's
                parameters.
        """
        import typing

        _type_map: dict[type, str] = {
            int: "integer",
            float: "number",
            bool: "boolean",
            str: "string",
            list: "array",
            dict: "object",
        }

        sig = inspect.signature(self.func)
        try:
            hints = typing.get_type_hints(self.func)
        except Exception:
            hints = {}

        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            # Prefer resolved hint over raw annotation
            annotation = hints.get(param_name, param.annotation)
            json_type = "string"
            if annotation is not inspect.Parameter.empty:
                json_type = _type_map.get(annotation, "string")

            properties[param_name] = {"type": json_type}

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return {
            "type": "object",
            "properties": properties,
            "required": required,
        }
