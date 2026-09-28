"""Utilities for implementing the abstract syntax tree"""

import math
from enum import Enum, auto
from typing import TypeAlias

from logprep.processor.calculator.ast.exceptions import (
    ParsingError,
)
from logprep.util.helper import FieldValue


class ValueType(Enum):
    """A enum specifying the type used in an expression.
    The AST emulates its own typing system through this enum.
    """

    BOOLEAN = auto()
    """A boolean type"""

    NUMBER = auto()
    """A numeric type (integer or float)"""

    def can_be_cast_to(self, other: "ValueType") -> bool:
        """Determine if a value can be casted into another type."""
        if self == other:
            return True
        if self == ValueType.NUMBER and other == ValueType.BOOLEAN:
            return True
        return False


Value: TypeAlias = int | float | bool


def parse_value(value: FieldValue, expected_type: ValueType) -> Value:
    """Parse a given value into the specified ValueType."""
    match expected_type:
        case ValueType.NUMBER:
            if isinstance(value, bool):
                raise ParsingError("Expected number got boolean.")
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, str):
                if value.upper() == "PI":
                    return math.pi
                if value.upper() == "E":
                    return math.e
                try:
                    return int(value)
                except ValueError:
                    pass
                try:
                    return float(value)
                except ValueError:
                    pass
            raise ParsingError(f"Could not parse input {value !r} to number")

        case ValueType.BOOLEAN:
            if isinstance(value, (bool, int, float)):
                return bool(value)
            raise ParsingError(f"Could not parse {value !r}.")
    raise ParsingError(f"Could not parse {value !r} to {expected_type}")


def read_hex_number(value: FieldValue) -> int:
    """Read a hex number from a given input."""
    if not isinstance(value, str):
        raise ParsingError(f"Failed to parse {value !r} as hex_number. String expected.")
    try:
        return int(value, 16)
    except (ValueError, TypeError) as error:
        raise ParsingError(f"Failed to parse {value !r} as hex_number.") from error
