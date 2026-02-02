from typing import TypeVar

from logprep.factory_error import InvalidConfigurationError

Key = TypeVar("Key")
Value = TypeVar("Value")


def convert_ordered_mapping_or_keep_mapping(
    dict_or_sequence: dict[Key, Value] | list[dict[Key, Value]],
) -> dict[Key, Value]:
    if isinstance(dict_or_sequence, dict):
        return dict_or_sequence

    if not isinstance(dict_or_sequence, list):
        raise InvalidConfigurationError("expected list")

    return convert_ordered_mapping(dict_or_sequence)


def convert_ordered_mapping(dicts: list[dict[Key, Value]]) -> dict[Key, Value]:
    ordered_mapping = {}
    for element in dicts:
        keys = list(element.keys())
        if len(keys) != 1:
            raise InvalidConfigurationError("dict has not exactly one key")
        if keys[0] in ordered_mapping:
            raise InvalidConfigurationError("dict already has key")
        ordered_mapping[keys[0]] = element[keys[0]]

    return ordered_mapping
