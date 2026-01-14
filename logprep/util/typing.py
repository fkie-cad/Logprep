"""
This module contains typing related helper functions
that are shared by different modules.
"""

from typing import Any, TypeGuard, TypeVar

T = TypeVar("T")


def is_list_of(val: list[Any], class_or_tuple: type[T]) -> TypeGuard[list[T]]:
    """Checks and statically asserts that a list has a specific element type

    Parameters
    ----------
    val : list[Any]
        The list to be checked
    class_or_tuple : type[T]
        The element type to be checked against

    Returns
    -------
    TypeGuard[list[T]]
        The type information that `val` is of this list type
    """
    return all(isinstance(obj, class_or_tuple) for obj in val)
