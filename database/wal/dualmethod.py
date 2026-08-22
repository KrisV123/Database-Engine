from typing import TypeVar, ParamSpec, Concatenate, Generic, overload
from functools import wraps
from collections.abc import Callable

P = ParamSpec('P')
I = TypeVar('I')
R = TypeVar('R')

class dualmethod(Generic[I, P, R]):
    """
    method decorator / data descriptor.
    Method can be called on instance or class at the same time.
    That swap logic must be handled inside a body of decorated function

    EXAMPLE:\n
        .. code-block:: python
        class A
            @dualmethod
            def funct(obj):
                if ininstance(obj, type):
                    ...
                else:
                    ...
    """

    def __init__(self, method: Callable[Concatenate[I | type[I], P], R]):
        self.method = method

    @overload
    def __get__(self, inst: I, owner: type[I]) -> Callable[P, R]: ...

    @overload
    def __get__(self, inst: None, owner: type[I]) -> Callable[P, R]: ...

    def __get__(self, inst: I | None, owner: type[I]) -> Callable[P, R]:
        @wraps(self.method)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if inst is None:
                return self.method(owner, *args, **kwargs)
            else:
                return self.method(inst, *args, **kwargs)
        return wrapper
