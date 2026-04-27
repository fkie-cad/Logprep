from collections.abc import Callable, Sequence
from typing import TypeVar

T = TypeVar("T")
Key = TypeVar("Key")
Value = TypeVar("Value")


def convert_ordered_mapping_or_keep_mapping(
    dict_or_sequence: dict[Key, Value] | Sequence[dict[Key, Value]],
) -> dict[Key, Value]:
    """Convert a list of key values to a single dict, with no reocurring keys
    and only single item dicts, if input is already singular dict, return early"""
    if isinstance(dict_or_sequence, dict):
        return dict_or_sequence

    if not isinstance(dict_or_sequence, Sequence):
        raise ValueError("expected sequence")

    return convert_ordered_mapping(dict_or_sequence)


def convert_ordered_mapping(dicts: Sequence[dict[Key, Value]]) -> dict[Key, Value]:
    """Convert a list of key values to a single dict, with no reocurring keys
    and only single item dicts"""
    ordered_mapping = {}
    for element in dicts:
        keys = list(element.keys())
        if len(keys) != 1:
            raise ValueError("dict has not exactly one key")
        if keys[0] in ordered_mapping:
            raise ValueError("dict already has key")
        ordered_mapping[keys[0]] = element[keys[0]]

    return ordered_mapping


def convert_ordered_tuples_with_factory(
    dicts: Sequence[dict[Key, Value]], factory: Callable[[Key, Value], T]
) -> Sequence[T]:
    """Converts a sequence of typically single-valued dicts into a sequence of objects,
    whereas each object represents an item and all items are represented.
    Keys can occur multiple times throughout the dicts and are kept as such.
    A typical use case is to transform a list of dicts into tuples, named tuples or dataclasses.


    Parameters
    ----------
    dicts : Sequence[dict[Key, Value]]
        The sequence of dicts to transform
    factory : Callable[[Key, Value], T]
        A factory function to be called for each item

    Returns
    -------
    Sequence[T]
        The sequence of produced objects by the factory
    """
    if any(len(d) > 1 for d in dicts):
        raise ValueError(f"entries are not allowed to have more than one mapping item: {dicts}")
    return [factory(key, value) for d in dicts for key, value in d.items()]


def convert_from_dict(constructor: type[T], data: T | dict) -> T:
    """Converter function which either constructs an instance of type :code:`T`
    by calling the given constructor with the kwargs from the data dict, or simply
    returns the already existing object instance if passed as data parameter.

    Parameters
    ----------
    constructor : type[T]
        A function accepting all kwargs from the potential data dict.
    data : T | dict
        Either already an instance, or a dict with all the relevant parameters
        for instantiation.

    Returns
    -------
    T
        An object of type :code:`T`
    """
    if isinstance(data, dict):
        return constructor(**data)
    return data
