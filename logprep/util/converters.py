from typing import TypeVar

Key = TypeVar("Key")
Value = TypeVar("Value")


def convert_ordered_mapping_or_keep_mapping(
    dict_or_sequence: dict[Key, Value] | list[dict[Key, Value]],
) -> dict[Key, Value]:
    """Convert a list of key Values to a single dict, with no reocurring keys and only single item dicts, if input is already singular dict, return early"""
    if isinstance(dict_or_sequence, dict):
        return dict_or_sequence

    if not isinstance(dict_or_sequence, list):
        raise ValueError("expected list")

    return convert_ordered_mapping(dict_or_sequence)


def convert_ordered_mapping(dicts: list[dict[Key, Value]]) -> dict[Key, Value]:
    """Convert a list of key Values to a single dict, with no reocurring keys and only single item dicts"""
    ordered_mapping = {}
    for element in dicts:
        keys = list(element.keys())
        if len(keys) != 1:
            raise ValueError("dict has not exactly one key")
        if keys[0] in ordered_mapping:
            raise ValueError("dict already has key")
        ordered_mapping[keys[0]] = element[keys[0]]

    return ordered_mapping
