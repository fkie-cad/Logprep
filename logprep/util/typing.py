"""
This module contains typing related helper functions
that are shared by different modules.
"""

from functools import _lru_cache_wrapper
from typing import Any, Callable, TypeGuard, TypeVar

T = TypeVar("T")


def is_list_of(val: list[Any], class_type: type[T]) -> TypeGuard[list[T]]:
    """Checks and statically asserts that a list has a specific element type

    Parameters
    ----------
    val : list[Any]
        The list to be checked
    class_type : type[T]
        The element type to be checked against

    Returns
    -------
    TypeGuard[list[T]]
        The type information that `val` is of this list type
    """
    return all(isinstance(obj, class_type) for obj in val)


def is_lru_cached(val: Callable) -> TypeGuard[_lru_cache_wrapper]:
    """Checks the given callable for being a cache wrapper
    (and thus having a :code:`cache_info` attribute)

    Parameters
    ----------
    val : Callable
        The object to check

    Returns
    -------
    TypeGuard[_lru_cache_wrapper]
        The type information that :code:`val` a cache wrapper
    """
    return isinstance(val, _lru_cache_wrapper)
