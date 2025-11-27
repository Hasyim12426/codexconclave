"""Unit tests for the Instrument subsystem."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from codexconclave.instruments.base import (
    BaseInstrument,
    InstrumentExecutionError,
    InstrumentResult,
    InstrumentValidationError,
)
from codexconclave.instruments.structured import StructuredInstrument

# ---------------------------------------------------------------------------
# Concrete test instruments
# ---------------------------------------------------------------------------


class EchoInstrument(BaseInstrument):
    """Simple instrument that echoes its input."""

    name: str = "echo"
    description: str = "Echo the input text."

    def execute(self, text: str = "") -> str:  # type: ignore[override]
        return f"ECHO: {text}"


class FailingInstrument(BaseInstrument):
    """Instrument that always raises."""

    name: str = "fail"
    description: str = "Always fails."

    def execute(self, **kwargs: Any) -> str:
        raise RuntimeError("deliberate failure")


class LimitedInstrument(BaseInstrument):
    """Instrument with max_uses=2."""

    name: str = "limited"
    description: str = "Limited uses."
    max_uses: int = 2

    def execute(self, **kwargs: Any) -> str:
        return "ok"


# ---------------------------------------------------------------------------
# InstrumentResult tests
# ---------------------------------------------------------------------------


class TestInstrumentResult:
    """Tests for the InstrumentResult model."""

    def test_creation(self) -> None:
        """InstrumentResult should be constructable with basic fields."""
        result = InstrumentResult(
            output="hello",
            cached=False,
            execution_time_ms=12.5,
            instrument_name="test",
        )
        assert result.output == "hello"
        assert result.cached is False
        assert result.execution_time_ms == 12.5
        assert result.instrument_name == "test"

    def test_default_cached_false(self) -> None:
        """cached should default to False."""
        result = InstrumentResult(output="x", instrument_name="test")
        assert result.cached is False


# ---------------------------------------------------------------------------
# BaseInstrument tests
# ---------------------------------------------------------------------------


class TestBaseInstrument:
    """Tests for BaseInstrument via EchoInstrument."""

    def test_execute_returns_string(self) -> None:
        """execute() should return a string."""
        inst = EchoInstrument()
        assert inst.execute(text="hello") == "ECHO: hello"

    def test_run_returns_instrument_result(self) -> None:
        """run() should return an InstrumentResult."""
        inst = EchoInstrument()
        result = inst.run(text="test")
        assert isinstance(result, InstrumentResult)
        assert result.output == "ECHO: test"

    def test_run_records_execution_time(self) -> None:
        """run() should record a non-negative execution time."""
        inst = EchoInstrument()
        result = inst.run(text="x")
        assert result.execution_time_ms >= 0

    def test_run_not_cached_by_default(self) -> None:
        """run() result should not be cached when cache_enabled=False."""
        inst = EchoInstrument()
        result = inst.run(text="x")
        assert result.cached is False

    def test_run_wraps_execute_exception(self) -> None:
        """run() should raise InstrumentExecutionError on failure."""
        inst = FailingInstrument()
        with pytest.raises(InstrumentExecutionError):
            inst.run()

    def test_max_uses_limit(self) -> None:
        """Instrument should raise when max_uses is exceeded."""
        inst = LimitedInstrument()
        inst.run()
        inst.run()
        with pytest.raises(InstrumentExecutionError, match="maximum"):
            inst.run()

    def test_schema_structure(self) -> None:
        """to_tool_schema() should return an OpenAI-compatible function schema."""
        inst = EchoInstrument()
        schema = inst.to_tool_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "echo"
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]

    def test_cache_enabled_serves_cached_result(self) -> None:
        """When cache_enabled, second call with same args uses cache."""
        inst = EchoInstrument(cache_enabled=True)
        first = inst.run(text="hello")
        second = inst.run(text="hello")
        assert first.cached is False
        assert second.cached is True
        assert first.output == second.output

    def test_cache_different_args_not_cached(self) -> None:
        """Different args should not use each other's cache entries."""
        inst = EchoInstrument(cache_enabled=True)
        r1 = inst.run(text="hello")
        r2 = inst.run(text="world")
        assert r1.cached is False
        assert r2.cached is False


# ---------------------------------------------------------------------------
# StructuredInstrument tests
# ---------------------------------------------------------------------------


def add(a: int, b: int) -> str:
    """Add two numbers and return the sum as a string."""
    return str(a + b)


def greet(name: str) -> str:
    """Say hello to name."""
    return f"Hello, {name}!"


class TestStructuredInstrument:
    """Tests for StructuredInstrument."""

    def test_from_function_uses_func_name(self) -> None:
        """from_function should use the function name as instrument name."""
        inst = StructuredInstrument.from_function(add)
        assert inst.name == "add"

    def test_from_function_uses_docstring(self) -> None:
        """from_function should use the docstring as description."""
        inst = StructuredInstrument.from_function(add)
        assert "Add two numbers" in inst.description

    def test_from_function_override_name(self) -> None:
        """from_function should accept a custom name."""
        inst = StructuredInstrument.from_function(add, name="adder")
        assert inst.name == "adder"

    def test_from_function_override_description(self) -> None:
        """from_function should accept a custom description."""
        inst = StructuredInstrument.from_function(add, description="My adder")
        assert inst.description == "My adder"

    def test_execute_calls_function(self) -> None:
        """execute() should invoke the wrapped function."""
        inst = StructuredInstrument.from_function(add)
        assert inst.execute(a=3, b=4) == "7"

    def test_execute_converts_non_str_to_str(self) -> None:
        """execute() should convert non-string return values."""

        def mul(a: int, b: int) -> int:  # returns int
            return a * b  # type: ignore[return-value]

        inst = StructuredInstrument.from_function(mul)
        result = inst.execute(a=3, b=4)
        assert result == "12"
        assert isinstance(result, str)

    def test_schema_infers_int_type(self) -> None:
        """Schema should infer 'integer' type from int annotations."""
        inst = StructuredInstrument.from_function(add)
        schema = inst.to_tool_schema()
        props = schema["function"]["parameters"]["properties"]
        assert props["a"]["type"] == "integer"
        assert props["b"]["type"] == "integer"

    def test_schema_required_params(self) -> None:
        """Parameters with no default should appear in required list."""
        inst = StructuredInstrument.from_function(add)
        required = inst.to_tool_schema()["function"]["parameters"]["required"]
        assert "a" in required
        assert "b" in required

    def test_args_schema_validation(self) -> None:
        """When args_schema is set, invalid inputs should raise."""

        class AddSchema(BaseModel):
            a: int
            b: int

        inst = StructuredInstrument.from_function(add)
        inst = StructuredInstrument(
            name="add",
            description="add",
            func=add,
            args_schema=AddSchema,
        )
        # Valid call
        assert inst.execute(a=1, b=2) == "3"

        # Invalid: missing required field
        with pytest.raises(InstrumentValidationError):
            inst.execute(a=1)
