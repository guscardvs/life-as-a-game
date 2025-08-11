from collections.abc import Awaitable, Callable
from typing import cast


def asserts_async[**P, T](
    func: Callable[P, T | Awaitable[T]],
) -> Callable[P, Awaitable[T]]:
    """
    Helper function to rectify type hints from asyncio redis.
    This is used to hint to the type checker that the function
    is asynchronous, even if it returns a synchronous value.
    """
    return cast(Callable[P, Awaitable[T]], func)
