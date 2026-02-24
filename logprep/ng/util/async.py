import asyncio
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar

T = TypeVar("T")
P = ParamSpec("P")


def create_task(
    factory: Callable[P, Coroutine[Any, Any, T]], *args: P.args, **kwargs: P.kwargs
) -> asyncio.Task[T]:
    """
    Wraps :code:`asyncio.create_task` to automatically assign a name derived from...

    Parameters
    ----------
    factory : Callable[P, Coroutine[Any, Any, T]]
        _description_

    Returns
    -------
    asyncio.Task[T]
        _description_
    """
    factory_self = getattr(factory, "__self__", None)
    name = (
        f"{factory_self.__class__.__name__}.{factory.__name__}"
        if factory_self is not None
        else f"{factory.__name__}"
    )
    return asyncio.create_task(factory(*args, **kwargs), name=name)
