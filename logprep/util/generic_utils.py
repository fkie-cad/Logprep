from collections.abc import Callable, Iterable
from typing import TypeVar

In = TypeVar("In")
Out = TypeVar("Out")


def partition_by(
    items: Iterable[In],
    predicate: Callable[[In], bool],
) -> tuple[list[In], list[In]]:
    fit: list[In] = []
    no_fit: list[In] = []
    for item in items:
        (fit if predicate(item) else no_fit).append(item)
    return fit, no_fit


def partition_map_by(
    items: Iterable[In],
    predicate: Callable[[In], bool],
    transform: Callable[[In], Out],
) -> tuple[list[Out], list[Out]]:
    fit: list[Out] = []
    no_fit: list[Out] = []
    for item in items:
        (fit if predicate(item) else no_fit).append(transform(item))
    return fit, no_fit
