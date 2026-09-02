import math
from enum import Enum, auto
from typing import Any

from logprep.processor.calculator.ast.exceptions import (
    ParsingError,
)

# NOTE: The AST emulates its own typing system through enums.


class ValueType(Enum):
    BOOLEAN = auto()
    NUMBER = auto()

    def can_be_cast_to(self, other: "ValueType") -> bool:
        if self == other:
            return True
        if self == ValueType.NUMBER and other == ValueType.BOOLEAN:
            return True
        return False


def parse_value(value: Any, expected_type: ValueType) -> Any:
    match expected_type:
        case ValueType.NUMBER:
            if isinstance(value, (int, float)):
                return value
            if isinstance(value, bool):
                raise ParsingError("Expected number got boolean.")
            if isinstance(value, str):
                if value.upper() == "PI":
                    return math.pi
                if value.upper() == "E":
                    return math.e
            try:
                return int(value)
            except (TypeError, ValueError):
                try:
                    return float(value)
                except (TypeError, ValueError) as error:
                    raise ParsingError(f"Could not parse input {value !r} to number") from error
        case ValueType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            raise ParsingError(f"Could not parse {value !r}.")
    raise ParsingError(f"Could not parse {value !r} to {expected_type}")


def read_hex_number(value: Any) -> int:
    try:
        return int(value, 16)
    except (ValueError, TypeError) as error:
        raise ParsingError(f"Failed to parse {value !r} as hex_number.") from error
