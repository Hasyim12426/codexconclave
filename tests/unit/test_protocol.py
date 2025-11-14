"""Unit tests for the Protocol enum."""

from __future__ import annotations

import pytest

from codexconclave.protocol import Protocol


class TestProtocol:
    """Tests for the Protocol execution-strategy enum."""

    def test_sequential_value(self) -> None:
        """Protocol.sequential should have value 'sequential'."""
        assert Protocol.sequential.value == "sequential"

    def test_hierarchical_value(self) -> None:
        """Protocol.hierarchical should have value 'hierarchical'."""
        assert Protocol.hierarchical.value == "hierarchical"

    def test_protocol_is_str(self) -> None:
        """Protocol members should be usable as plain strings."""
        assert Protocol.sequential == "sequential"
        assert Protocol.hierarchical == "hierarchical"

    def test_from_string_sequential(self) -> None:
        """Should be constructable from the string value."""
        assert Protocol("sequential") is Protocol.sequential

    def test_from_string_hierarchical(self) -> None:
        """Should be constructable from the string value."""
        assert Protocol("hierarchical") is Protocol.hierarchical

    def test_invalid_value_raises(self) -> None:
        """An unknown value should raise ValueError."""
        with pytest.raises(ValueError):
            Protocol("parallel")

    def test_members_count(self) -> None:
        """There should be exactly two protocol variants."""
        assert len(Protocol) == 2

    def test_str_representation(self) -> None:
        """str(Protocol.sequential) should return the value string."""
        assert str(Protocol.sequential) == "sequential"
