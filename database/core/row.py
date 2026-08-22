from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar, overload
from database.core.types import AcceptTypes

class RowList[T = AcceptTypes](list[T]):
    """
    Class represents one tuple from database,
    but each element can be indexed by it's attribute name
    """

    S_add = TypeVar('S_add', bound=AcceptTypes)
    O_add = TypeVar('O_add', bound=AcceptTypes)
    T_copy = TypeVar('T_copy', bound=AcceptTypes)

    def __init__(self, iterable: Iterable[T] | None=None, **attributes: int):
        super().__init__() if iterable is None else super().__init__(iterable)
        self._attributes: dict[str, int] = attributes

    @property
    def attributes(self) -> dict[str, int]:
        return self._attributes

    def __eq__(self: RowList[T_ident], other: RowList[T_ident]) -> bool: #type:ignore[overwrite]
        return (isinstance(other, RowList) and list(self) == list(other) and
                self.attributes == other.attributes)

    def __ne__(self: RowList[T_ident], other: RowList[T_ident]) -> bool: #type:ignore[overwrite]
        return not self.__eq__(other)

    def __len__(self) -> int:
        return super().__len__()

    @overload
    def __getitem__(self, key: int) -> T: ...

    @overload
    def __getitem__(self, key: str) -> T: ...

    def __getitem__(self, key: int | str) -> T: #type:ignore[overwrite]
        if isinstance(key, int):
            return super().__getitem__(key)
        elif isinstance(key, str):
            return super().__getitem__(self._attributes[key])
        raise KeyError(key)

    @overload
    def __setitem__(self, key: int, value: T) -> None: ...

    @overload
    def __setitem__(self, key: str, value: T) -> None: ...

    def __setitem__(self, key: int | str, value: T) -> None: #type:ignore[overwrite]
        if isinstance(key, int):
            super().__setitem__(key, value)
        elif isinstance(key, str):
            super().__setitem__(self._attributes[key], value)
        else:
            raise KeyError(key)

    def __add__(self: RowList[S_add], other: RowList[O_add]) -> RowList[S_add | O_add]: #type:ignore[overwrite]
        """sum don't work properly on RowLists with same attributes"""

        if not isinstance(other, RowList):
            raise TypeError("only two RowLists can be summed")

        new_list = RowList(super().__add__(other))
        new_list._attributes.update(self._attributes)
        attr_updt = {key: value + len(self) for key, value in other._attributes.items()}
        new_list._attributes.update(attr_updt)
        return new_list

    def append_named(self, val: T, attr: str) -> None:
        self._attributes[attr] = len(self)
        super().append(val)

    def pop_named(self, key: str) -> T:
        try:
            del_idx = self._attributes.pop(key)
            value = super().pop(del_idx)
        except KeyError as e:
            raise KeyError(f'attribute {e} not inside RowList')

        for attr, idx in self._attributes.items():
            if idx > del_idx:
                self._attributes[attr] = idx - 1
        return value

    def append(self, _: object) -> None:
        raise NotImplementedError('append disabled. Did you mean append_named?')

    def pop(self, _: object=-1):
        raise NotImplementedError('append disabled. Did you mean pop_named?')

    def copy(self: RowList[T_copy]) -> RowList[T_copy]: #type:ignore[overwrite]
        """creates shalow copy of RowList"""

        return RowList(self, **self.attributes)