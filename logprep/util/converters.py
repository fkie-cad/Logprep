from typing import TypeVar

from logprep.factory_error import InvalidConfigurationError

KeyTypeT = TypeVar("KeyTypeT")
ValueTypeT = TypeVar("ValueTypeT")


def convert_ordered_mapping_or_skip(
    x: dict[KeyTypeT, ValueTypeT] | list[dict[KeyTypeT, ValueTypeT]],
) -> dict[KeyTypeT, ValueTypeT]:
    if isinstance(x, dict):
        return x

    if not isinstance(x, list):
        raise InvalidConfigurationError("expected list")

    return convert_ordered_mapping(x)


def convert_ordered_mapping(dicts: list[dict[KeyTypeT, ValueTypeT]]) -> dict[KeyTypeT, ValueTypeT]:
    ordered_mapping = {}
    for element in dicts:
        keys = list(element.keys())
        if len(keys) != 1:
            raise InvalidConfigurationError("dict has not exactly one key")
        if keys[0] in ordered_mapping:
            raise InvalidConfigurationError("dict already has key")
        ordered_mapping[keys[0]] = element[keys[0]]

    return ordered_mapping
