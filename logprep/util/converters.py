from typing import TypeVar

from logprep.factory_error import InvalidConfigurationError

VALUE_TYPE = TypeVar("VALUE_TYPE")
KEY_TYPE = TypeVar("KEY_TYPE")


def merge_dicts(
    x: list[dict[KEY_TYPE, VALUE_TYPE]],
) -> dict[KEY_TYPE, VALUE_TYPE]:
    res = {}
    for item in x:
        keys = list(item.keys())
        if len(keys) != 1:
            raise InvalidConfigurationError("dict has not exactly one key")
        if keys[0] in res:
            raise InvalidConfigurationError("dict already has key")
        res[keys[0]] = item[keys[0]]

    return res


def convert_ordered_mapping(x: dict[KEY_TYPE, VALUE_TYPE] | list[dict[KEY_TYPE, VALUE_TYPE]]):
    if isinstance(x, dict):
        return x

    if not isinstance(x, list):
        raise InvalidConfigurationError("expected list")

    return merge_dicts(x)
