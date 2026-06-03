from __future__ import annotations
import struct
import mmap
import inspect
from pathlib import Path
from math import ceil
from functools import cache
from warnings import warn
from contextlib import ExitStack

from collections.abc import Iterable
from collections import defaultdict
from typing import Literal, overload, TypeVar, cast, Any, get_type_hints

from database.tools.literal_parser import (
    tokenize, SJ_alg, build_AST, Evaluator, get_values 
)
from database.tools.wal_comp import _LOG_INST

AcceptTypes = int | float | bool | str | bytes | None

T_diff = TypeVar('T_diff')
T_ident = TypeVar('T_ident')
P_join = TypeVar('P_join')
B_join = TypeVar('B_join')

class RowList[T = AcceptTypes](list[T]):
    """
    Class represents one tuple from database,
    but each element can be indexed by it's attribute name
    """

    S_add = TypeVar('S_add')
    O_add = TypeVar('O_add')
    T_copy = TypeVar('T_copy')

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


class Table[T = AcceptTypes](dict[tuple, RowList[T]]):
    """
    Class represents one table in database where dictionary key
    is primary key and value in tuple of the database represented
    with custom ColumnLine class. It's just dictionary with additional methods
    """

    T_attrs = TypeVar('T_attrs')

    def __init__(self,
                 dictionary: dict[tuple, RowList[T]],
                 **attributes: int):
        super().__init__() if dictionary is None else super().__init__(dictionary)
        self._attributes = attributes

    @property
    def attributes(self) -> dict[str, int]:
        return self._attributes

    def __eq__(self: Table[T_ident], other: Table[T_ident]) -> bool: #type:ignore[overwrite]
        return (isinstance(other, Table) and dict(self) == dict(other) and
                self.attributes == other.attributes)

    def __ne__(self: Table[T_ident], other: Table[T_ident]) -> bool: #type:ignore[overwrite]
        return not self.__eq__(other)

    def _get_attr_idx(self, arg: int) -> str:
        """
        return name of attribute from dictionary self._attributes
        with specified index
        """

        if self.attributes is None:
            raise AttributeError("table does not have attributes")

        for attr, idx in self.attributes.items():
            if idx == arg:
                return attr
        raise IndexError("table don't have that index")

    def project(self, *args: str | int) -> Table[T]:
        """
        filters columns from Table. Columns can be chosen by attribute name
        or index. Returns new table
        """

        attributes: dict[str, int] = {}
        for order, arg in enumerate(args):
            if isinstance(arg, str):
                attributes[arg] = order
            else:
                assert isinstance(arg, int)
                attr = self._get_attr_idx(arg)
                attributes[attr] = arg

        new_table: Table[T] = Table({}, **attributes)
        for key, line in self.items():
            new_column: RowList[T] = RowList()
            for arg in args:
                if isinstance(arg, str):
                    new_column.append_named(line[arg], arg)
                else:
                    assert isinstance(arg, int)
                    idx = self._get_attr_idx(arg)
                    new_column.append_named(line[arg], idx)
            new_table[key] = new_column
        return new_table

    def select(self: Table[T_attrs], expr: str) -> Table[T_attrs]:
        """
        filters rows, for which expresion evaluates to True.
        Returns new table
        """

        vvars = [attrib for attrib in self.attributes if attrib in expr]
        ast = build_AST(SJ_alg(tokenize(expr)))
        return Table({
            key: line for key, line in self.items()
            if Evaluator({var: line[var] for var in vvars}).interpret(ast)},
            **self.attributes
        )

    def union(self: Table[T_attrs], table: Table[T_attrs]) -> Table[T_attrs]:
        """
        merge two tables with same attributes together.
        Returns new table
        """

        if self.attributes != table.attributes:
            raise AttributeError("attributes from tables don't match")

        new_table = Table(self, **self.attributes)
        new_table |= table
        return new_table

    def difference(self: Table[T_diff], table: Table[T_diff]) -> Table[T_diff]:
        """hash based difference between two tables. Returns new table"""

        if self.attributes != table.attributes:
            raise AttributeError("attributes from tables don't match")

        hash_table = defaultdict(list)
        if len(self) > len(table):
            for key, column in table.items():
                hash_table[hash((key, tuple(column)))].append((key, column))

            new_table = Table[T_diff]({}, **self.attributes)
            for key, column in self.items():
                col_hash = hash((key, tuple(column)))
                if (col_hash not in hash_table or
                    (key, column) not in hash_table[col_hash]):
                    new_table[key] = column
                if (col_hash in hash_table and
                    (key, column) not in hash_table[col_hash]):
                    warn('ERROR: hash colision in difference operation')
        else:
            for key, column in self.items():
                hash_table[hash((key, tuple(column)))].append((key, column))

            for key, column in table.items():
                col_hash = hash((key, tuple(column)))
                if col_hash in hash_table:
                    key_col_tup = (key, column)
                    if key_col_tup in hash_table[col_hash]:
                        hash_table[col_hash].remove(key_col_tup)
                        if len(hash_table[col_hash]) == 0:
                            del hash_table[col_hash]
                    else:
                        warn('ERROR: hash colision in difference operation')

            new_table = Table[T_diff]({
                key: column
                for bucket in hash_table.values()
                for key, column in bucket},
                **self.attributes
            )
        return new_table


    class _JoinUtils:
        """helper methods for join method"""

        type JoinType = Literal['INNER', 'LEFT', 'RIGHT']

        def get_flagged_attrs(self, attrs: dict[str, int],
                              same_attrs: list[str],
                              postfix: str) -> dict[str, int]:
            """set postfix to flagged attributes. Internal method, not meant to be used"""

            return {(attr + postfix if attr in same_attrs else attr): idx
                    for attr, idx in attrs.items()}
        
        def setup_build_side(self, switched: bool, typ: JoinType) -> JoinType:
            """
            changing rotation for smaller table based on equivalency of joins
            for bigger table on build side
            """

            if switched and typ != 'INNER':
                typ = 'RIGHT' if typ == 'LEFT' else 'LEFT'
            return typ

        def create_join_table_attrs(self,
                                    typ: JoinType,
                                    probe: Table[P_join], build: Table[B_join],
                                    switched: bool) -> dict[str, int]:
            """
            merge two attribute dictionaries into one based on join type
            and rotation of tables. Internal method, not meant to be used
            """

            typ = self.setup_build_side(switched, typ)
            same_attrs = [attr for attr in probe.attributes if attr in build.attributes]
            if typ in ('LEFT', 'RIGHT'):
                if not switched:
                    flag_probe_attrs_1 = self.get_flagged_attrs(probe.attributes, same_attrs, '.1')
                    flag_build_attrs_2 = self.get_flagged_attrs(build.attributes, same_attrs, '.2')
                    attrs = flag_probe_attrs_1 | flag_build_attrs_2
                else:
                    flag_probe_attrs_2 = self.get_flagged_attrs(probe.attributes, same_attrs, '.2')
                    flag_build_attrs_1 = self.get_flagged_attrs(build.attributes, same_attrs, '.1')
                    attrs = flag_build_attrs_1 | flag_probe_attrs_2

                for order, key in enumerate(attrs.keys()):
                    attrs[key] = order
            else:
                if switched:
                    attrs = build.attributes | probe.attributes
                else:
                    attrs = probe.attributes | build.attributes
                idx = 0
                for key in attrs.copy().keys():
                    if key in same_attrs:
                        attrs.pop(key)
                    else:
                        attrs[key] = idx
                        idx += 1
            return attrs

        @overload
        def join_engine(self,
                        typ: Literal['INNER'],
                        probe: Table[P_join], build: Table[B_join],
                        switched: bool, *attrs: str) -> Table[P_join | B_join]: ...
        
        @overload
        def join_engine(self,
                        typ: Literal['LEFT', 'RIGHT'],
                        probe: Table[P_join], build: Table[B_join],
                        switched: bool, *attrs: str) -> Table[P_join | B_join | None]: ...

        def join_engine(self,
                        typ: JoinType,
                        probe: Table[P_join], build: Table[B_join],
                        switched: bool, *attrs: str) -> Table[P_join | B_join] | Table[P_join | B_join | None]:
            """
            method that calculate hash join based on build and probe table.
            Not meant to be called. Rather use join
            """

            if typ not in ('INNER', 'LEFT', 'RIGHT'):
                raise AttributeError('join type does not exist or not supported')

            new_attributes = self.create_join_table_attrs(typ, probe, build, switched)
            typ = self.setup_build_side(switched, typ)
            same_attrs = [attr for attr in probe.attributes if attr in build.attributes]

            hash_table: defaultdict[int, list[tuple[tuple[B_join, ...], RowList[B_join]]]] = defaultdict(list)
            for key, column in build.items():
                hash_table[hash(tuple(column[attr] for attr in attrs))].append((key, column))

            new_inner_table = Table[B_join | P_join]({}, **new_attributes) 
            new_outer_table = Table[B_join | P_join | None]({}, **new_attributes)
            surr_pk = 0
            used_hash = set()
            for key, column in probe.items():
                bucket_hash = hash(tuple(column[attr] for attr in attrs))

                if typ == 'INNER':
                    if bucket_hash not in hash_table:
                        continue
                    for hash_pk, hash_col in hash_table[bucket_hash]:
                        build_col = hash_col.copy()
                        for attr in hash_col._attributes:
                            if attr in same_attrs:
                                build_col.pop_named(attr)

                        probe_col = column.copy()
                        for attr in column._attributes:
                            if attr in same_attrs:
                                probe_col.pop_named(attr)

                        if switched:
                            new_inner_table[hash_pk + key] = build_col + probe_col
                        else:
                            new_inner_table[key + hash_pk] = probe_col + build_col

                if typ == 'LEFT':
                    if bucket_hash not in hash_table:
                        if switched:
                            build_col_attr = self.get_flagged_attrs(
                                                build.attributes, same_attrs, '.1')
                            probe_col_attr = self.get_flagged_attrs(
                                                column._attributes, same_attrs, '.2')
                        else:
                            build_col_attr = self.get_flagged_attrs(
                                                build.attributes, same_attrs, '.2')
                            probe_col_attr = self.get_flagged_attrs(
                                                column._attributes, same_attrs, '.1')

                        length = len(build.attributes)
                        build_col = cast(RowList[B_join | None], RowList([None] * length, **build_col_attr))
                        probe_col = RowList[P_join](column, **probe_col_attr)

                        if switched:
                            new_outer_table[(surr_pk,)] = build_col + probe_col
                        else:
                            new_outer_table[(surr_pk,)] = probe_col + build_col
                        surr_pk += 1
                    else:
                        for _, hash_col in hash_table[bucket_hash]:
                            if switched:
                                build_col_attr = self.get_flagged_attrs(
                                                    build.attributes, same_attrs, '.1')
                                probe_col_attr = self.get_flagged_attrs(
                                                    column._attributes, same_attrs, '.2')
                            else:
                                build_col_attr = self.get_flagged_attrs(
                                                    build.attributes, same_attrs, '.2')
                                probe_col_attr = self.get_flagged_attrs(
                                                    column._attributes, same_attrs, '.1')

                            build_col = RowList[B_join | None](hash_col, **build_col_attr)
                            probe_col = RowList[P_join | None](column, **probe_col_attr)

                            if switched:
                                new_outer_table[(surr_pk,)] = build_col + probe_col
                            else:
                                new_outer_table[(surr_pk,)] = probe_col + build_col
                            surr_pk += 1

                if typ == 'RIGHT':
                    if bucket_hash not in hash_table:
                        continue
                    for hash_pk, hash_col in hash_table[bucket_hash]:
                        if switched:
                            build_col_attr = self.get_flagged_attrs(
                                                build.attributes, same_attrs, '.1')
                            probe_col_attr = self.get_flagged_attrs(
                                                column._attributes, same_attrs, '.2')
                        else:
                            build_col_attr = self.get_flagged_attrs(
                                                build.attributes, same_attrs, '.2')
                            probe_col_attr = self.get_flagged_attrs(
                                                column._attributes, same_attrs, '.1')

                        probe_col = RowList[P_join | None](column, **probe_col_attr)
                        build_col = RowList[B_join | None](hash_col, **build_col_attr)

                        if switched:
                            new_outer_table[(surr_pk,)] = build_col + probe_col
                        else:
                            new_outer_table[(surr_pk,)] = probe_col + build_col
                        surr_pk += 1
                        used_hash.add(bucket_hash)

            if typ == 'RIGHT':
                if switched:
                    probe_col_attr = self.get_flagged_attrs(
                                                probe.attributes, same_attrs, '.2')
                else:
                    probe_col_attr = self.get_flagged_attrs(
                                                probe.attributes, same_attrs, '.1')

                length = len(probe.attributes)
                probe_col = cast(RowList[P_join | None], RowList([None] * length, **probe_col_attr))
                for hash_key, hash_bucket in hash_table.items():
                    if hash_key in used_hash:
                        continue
                    for _, hash_col in hash_bucket:
                        if switched:
                            build_col_attr = self.get_flagged_attrs(
                                                hash_col.attributes, same_attrs, '.1')
                        else:
                            build_col_attr = self.get_flagged_attrs(
                                                hash_col.attributes, same_attrs, '.2')

                        build_col = RowList(hash_col, **build_col_attr)
                        if switched:
                            new_outer_table[(surr_pk,)] = build_col + probe_col
                        else:
                            new_outer_table[(surr_pk,)] = probe_col + build_col
                        surr_pk += 1
            return new_inner_table if typ == 'INNER' else new_outer_table
    
    @overload
    def join(self: Table[B_join], typ: Literal['INNER'], table: Table[P_join], *attrs: str
                                    ) -> Table[B_join | P_join]: ...
    
    @overload
    def join(self: Table[B_join], typ: Literal['LEFT', 'RIGHT'], table: Table[P_join], *attrs: str
                                    ) -> Table[B_join | P_join | None]: ...

    def join(self: Table[B_join], typ: _JoinUtils.JoinType, table: Table[P_join], *attrs: str
                                    ) -> Table[B_join | P_join] | Table[B_join | P_join | None]:
        """
        Hash based join that can handle INNER, LEFT, RIGHT join.

        In INNER case, table will have composite key from each table
        as dict key and combined table in dict value. Merging attribute
        will be skipped in values

        In LEFT, RIGHT case, table will have surrogate key as dict key
        in range [0, 1,..] and combined table in dict value also with
        keys from tables. Attributes with same name will get postfix
        '.1' for the left table and '.2' for the right table
        """

        utils = Table._JoinUtils()
        if len(self) >= len(table):
            return utils.join_engine(typ, self, table, False, *attrs)
        else:
            return utils.join_engine(typ, table, self, True, *attrs)


class BaseModelMeta(type):
    def __new__(cls, name: str, bases: tuple, namespace: dict):
        if (name not in ['LowBaseModel', 'HighBaseModel'] and
            '__init__' not in namespace.keys()):
            raise AttributeError('__init__ method not defined')

        for cls_param in namespace.keys():
            if cls_param == '__init__':
                init = inspect.signature(namespace[cls_param])

                for var in init.parameters.values():
                    if var.name == 'self' or var.annotation is not inspect.Signature.empty:
                        continue
                    raise AttributeError(
                        'input in __init__ method needs to have type annotation'
                    )
                namespace['__slots__'] = [x for x in init.parameters if x != 'self']
                break

        if '_packer' not in namespace.keys():
            namespace['_packer'] = None

        return super().__new__(cls, name, bases, namespace)


class LowBaseModel(metaclass=BaseModelMeta):
    try:
        # for POSIX platforms
        _os_pg_align = os.sysconf("SC_PAGE_SIZE") #type:ignore
    except:
        # for Windows platform
        _os_pg_align = mmap.ALLOCATIONGRANULARITY #type:ignore

    byte_model: str = ''
    path: Path = Path()
    primary_key: list[str] = ['']
    precalc_table = True # precalculate table for first zero in byte
    __slots__ = [] # variable created in metaclass
    _packer: struct.Struct | None # variable created in metaclass

    @classmethod
    def get_packer(cls) -> struct.Struct:
        """
        cache precompiled packer object with singleton pattern.
        Use this instead of _packer
        """

        if cls._packer is None:
            cls._packer = struct.Struct(cls.byte_model)
        return cls._packer

    # mainly for documentation but is also used in code
    STRUCT_FORMAT_INFO: dict[str, dict[str, str | int]] = {
        'x': {'c_type': 'pad byte',           'py_type': 'None',  'size': 1},
        'c': {'c_type': 'char',               'py_type': 'bytes', 'size': 1},
        'b': {'c_type': 'signed char',        'py_type': 'int',   'size': 1},
        'B': {'c_type': 'unsigned char',      'py_type': 'int',   'size': 1},
        '?': {'c_type': '_Bool',              'py_type': 'bool',  'size': 1},
        'h': {'c_type': 'short',              'py_type': 'int',   'size': 2},
        'H': {'c_type': 'unsigned short',     'py_type': 'int',   'size': 2},
        'i': {'c_type': 'int',                'py_type': 'int',   'size': 4},
        'I': {'c_type': 'unsigned int',       'py_type': 'int',   'size': 4},
        'l': {'c_type': 'long',               'py_type': 'int',   'size': 4},
        'L': {'c_type': 'unsigned long',      'py_type': 'int',   'size': 4},
        'q': {'c_type': 'long long',          'py_type': 'int',   'size': 8},
        'Q': {'c_type': 'unsigned long long', 'py_type': 'int',   'size': 8},
        'f': {'c_type': 'float',              'py_type': 'float', 'size': 4},
        'd': {'c_type': 'double',             'py_type': 'float', 'size': 8},
        's': {'c_type': 'char[]',             'py_type': 'bytes', 'size': 'variable'},
        'p': {'c_type': 'pascal string',      'py_type': 'bytes', 'size': 'variable'}
    }

    placeholder = {
        'None': None,
        'bytes': b'\x00',
        'int': 0,
        'float': 1.0,
        'bool': False
    }

    @staticmethod
    def sanitize(bstream: bytes) -> bytes:
        """wrapper method. Returns bstream withoud leading zero bytes"""

        return bstream.rstrip(b'\x00')

    @classmethod
    def sanitize_str(cls, strg: str) -> str:
        """
        clean input from string like single question marks.
        If don't have any, behaves like echo function (identity)
        """

        return strg[1:-1] if len(strg) > 1 and strg[0] == "'" and strg[-1] == "'" else strg

    def getstate(self) -> bytes:
        """change instance into bytes"""

        attrs = []
        prefix = bytearray(b'\x00' * self.get_mask_len())
        for idx, attr in enumerate(self.__slots__):
            val = getattr(self, attr)

            if val is None:
                self._flip_prefix_bit(prefix, idx)
                ctype = self.get_attr_ctype(attr)[-1]
                length: int | str = self.STRUCT_FORMAT_INFO[ctype]['size']
                if isinstance(length, str):
                    length = int(self.get_byte_model_list()[idx][:-1])
                if length is not None:
                    py_type = self.STRUCT_FORMAT_INFO[ctype]['py_type']
                    assert isinstance(py_type, str)
                    plcholder = self.placeholder[py_type]
                    attrs.append(plcholder)
                else:
                    raise TypeError(
                        'size in STRUCT_FORMAT_INFO should not have None value'
                    )
                continue

            attrs.append(val.encode('utf-8')) if isinstance(val, str) else attrs.append(val)
        return prefix + self.get_packer().pack(*attrs)

    @classmethod
    def setstate(cls, bstream: bytes) -> LowBaseModel:
        """change bytes into instance based on struct model from the class"""

        prefix_len = cls.get_mask_len()
        prefix = bstream[:prefix_len]
        data = cls.get_packer().unpack(bstream[prefix_len:])
        decode_data = []
        for idx, val in enumerate(data):
            if cls.check_none_value(prefix, cls.__slots__[idx]):
                val = None
            elif isinstance(val, bytes):
                val = cls.sanitize(val).decode('utf-8')
            decode_data.append(val)

        return cls(*decode_data)

    T = TypeVar('T')

    @classmethod
    def from_row(cls: type[T], row: RowList[AcceptTypes] | RowList[Any]) -> T:
        """
        method to pass RowList to model constructor without type errors

        WARNING: this method is not type save.
        Ensure, that params in RowList are compatible with model.
        """
        return cls(*row)

    def __str__(self) -> str:
        """return string of variables and values from object"""

        return ''.join(f'{key}: {getattr(self, key)}\r\n' for key in self.__slots__)

    @classmethod
    def read_bytes(cls, start: int, end: int) -> bytes:
        """return bytes from start point to end point"""

        start_align = (start // cls._os_pg_align) * cls._os_pg_align

        with (open(cls.path / 'data/data.bin', 'rb') as f,
              mmap.mmap(f.fileno(),
                        end - start_align,
                        access=mmap.ACCESS_READ,
                        offset = start_align) as mm):
            rel_start = start - start_align
            return mm[rel_start: rel_start + (end - start)]

    @classmethod
    def _write_bytes(cls, start: int, end: int, txt: bytes) -> None:
        """write bytes from start point to end point. Not recomended to use"""

        start_align = (start // cls._os_pg_align) * cls._os_pg_align

        with (open(cls.path / 'data/data.bin', 'r+b') as f,
              mmap.mmap(f.fileno(),
                        end - start_align,
                        access=mmap.ACCESS_WRITE,
                        offset = start_align) as mm):
            rel_start = start - start_align
            mm[rel_start: rel_start + (end - start)] = txt

    @classmethod
    @cache
    def inst_len(cls) -> int:
        """return size of instance of database in bytes"""

        return cls.get_mask_len() + struct.calcsize(cls.byte_model)

    @classmethod
    @cache
    def get_byte_model_list(cls) -> list[str]:
        """return list of every C type from cls.byte_model in list"""

        type_list, num_list = [], []
        for char in cls.byte_model:
            if char == ' ':
                continue
            if char.isdigit():
                num_list.append(char)
            elif isinstance(char, str):
                if char in ('s', 'p') and len(num_list) == 0:
                    raise AttributeError(
                        'invalid byte model. Types s and p need to have byte ammount'
                    )
                typ = ''.join(num_list) + char
                type_list.append(typ)
                num_list = []
        return type_list

    @classmethod
    @cache
    def get_attr_ord(cls, attr: str) -> int:
        """return attribute order from database. Not recomended to use"""

        count = 0
        for val in cls.__slots__:
            if val == attr:
                break
            else:
                count += 1
            if count == len(cls.__slots__):
                raise AttributeError('attribute not inside a model')
        return count

    @classmethod
    @cache
    def get_offset(cls, attr: str) -> int:
        """
        returns parameter offset in bytes.
        Couting starts from first attribute, not biggining of mask.
        Not recomended to use
        """

        ctype_list = cls.get_byte_model_list()
        offset = 0
        for idx, i in enumerate(cls.__slots__):
            if i == attr:
                break
            else:
                bsize = struct.calcsize(ctype_list[idx])
                offset += bsize
        return offset

    @classmethod
    @cache
    def get_attr_ctype(cls, attr: str) -> str:
        """return C type of an attribute"""

        type_list = cls.get_byte_model_list()
        return type_list[cls.get_attr_ord(attr)]

    @classmethod
    def get_bitmask_prefix(cls, offset: int) -> bytes:
        """return bytes, that represents offset"""

        bit_len = len(cls.__slots__)
        byte_len = ceil(bit_len / 8)
        return cls.read_bytes(offset, offset + byte_len)

    @classmethod
    def _flip_prefix_bit(cls, bitmask: bytearray, attr_ord: int) -> bytearray:
        """
        return prefix_mask with flipped bit.
        Internal method, not meant to be used
        """

        segment, offset = divmod(attr_ord, 8)
        bitmask[segment] ^= (1 << (7 - offset))
        return bitmask

    @classmethod
    @cache
    def get_mask_len(cls) -> int:
        """returns mask size in bytes"""

        bit_len = len(cls.__slots__)
        return ceil(bit_len / 8)

    @classmethod
    def check_none_value(cls, prefix: bytes, attr: str) -> bool:
        """checks if parameter have setted null value in prefix"""

        attr_ord = cls.get_attr_ord(attr)
        segment, offset = divmod(attr_ord, 8)
        return prefix[segment] & (1 << (7 - offset)) != 0

    @classmethod
    def is_deleted_flag(cls, pnt: int, mm: mmap.mmap) -> bool:
        """
        check if bit in tombstone is set to deleted.
        Pnt is first byte of instance in database
        (in database, 1 means is included, 0 means missing)
        """

        if pnt < 0:
            raise IndexError("Function can't handle negative indexes")

        inst_len = cls.inst_len()
        if pnt % inst_len != 0:
            raise IndexError('Pointer not on start of instance')

        inst_ord = pnt // inst_len
        segment, offset = divmod(inst_ord, 8)

        if segment >= len(mm) or len(mm) == 0:
            raise IndexError('Pointer check_deleted_flag out of range')
        return (False if mm[segment] & (1 << (7 - offset)) != 0 else True)

    @classmethod
    def _add_tombstone_flag(cls) -> None:
        """
        Add new bit with new byte at the end of tombstone.map.
        Internal method, not meant to be used

        NEEDS TO BE TESTED!
        """

        data_size = (cls.path / 'data/data.bin').stat().st_size
        tomb_path = cls.path / 'data/tombstone.map'

        inst_len = cls.inst_len()
        ammount = data_size // inst_len

        if ammount % 8 != 0:
            inst_ord = ammount // inst_len
            segment, offset = divmod(inst_ord, 8)
            align_offset = (segment // cls._os_pg_align) * cls._os_pg_align
            rel_segment = segment - align_offset
            with (open(tomb_path, 'r+b') as f,
                  mmap.mmap(f.fileno(),
                            rel_segment + 1,
                            access=mmap.ACCESS_WRITE,
                            offset = align_offset) as mm):
                mm[-1] |= (1 << (7 - offset))
        else:
            with open(tomb_path, 'a+b') as f:
                f.write(bytes([1 << 7]))

    @classmethod
    def _set_tombstone_flag(cls, pnt: int | None) -> None:
        """
        Set bit in tombstone file to 1 (Exists). Pointer represents
        offset in data.bin. If pointer is set to None,
        it will add new byte and set bit to 1.
        Internal method, not meant to be used
        """
        
        tomb_path = cls.path / 'data/tombstone.map'
        if pnt is None:
            with open(tomb_path, 'a+b') as f:
                f.write(bytes([1 << 7]))
        else:
            inst_len = cls.inst_len()
            if pnt % inst_len != 0:
                raise IndexError('Pointer not on start of instance')

            inst_ord = pnt // inst_len
            segment, offset = divmod(inst_ord, 8)
            align_offset = (segment // cls._os_pg_align) * cls._os_pg_align
            rel_segment = segment - align_offset
            with (open(tomb_path, 'r+b') as f,
                  mmap.mmap(f.fileno(),
                            rel_segment + 1,
                            access=mmap.ACCESS_WRITE,
                            offset = align_offset) as mm):
                mm[rel_segment] |= (1 << (7 - offset))


    class _EmptySpaceUtils:
        """helper methods for find_empty_space method"""

        def __init__(self, outer: type[LowBaseModel]):
            self._outer = outer

        @cache
        def byte_256_error(self) -> ValueError:
            return ValueError(
                """offset is None, what should be impossible
                (fst_zero_table returned 255 byte, which don't have zero)"""
            )

        @cache
        def calc_fst_zero_table(self) -> dict[int, int | None]:
            """
            Precalculate lookup table for first zero in every byte.
            None only for byte 255. Shouldn't be gotten
            """

            return {
                byte: (8 - int((~byte) & 0b11111111).bit_length()) for byte in range(255)
            } | {255: None}

        def pos_constructor(self, segment: int | None, offset: int | None) -> int | None:
            """
            construct return value for find_empty_space method.
            Internal method, no point in using it
            """

            return (
                (segment * 8 + offset) * self._outer.inst_len()
                if segment is not None and offset is not None
                else None
            )

        def smaller_blocks(self,
                           mv: memoryview,
                           begin_segment: int,
                           begin_offset: int,
                           end_segment: int | None,
                           precalc_table: bool) -> tuple[int | None, int | None]:
            """
            subpart of find empty space. Searching edges at the start and the end
            of find_empty_space smaller then unsigned long long int.
            Internal method, no point in using it.
            """

            segment: int | None = None
            offset: int | None = None
            for idx, byte in enumerate(mv[begin_segment:end_segment]):
                if byte == 0b11111111:
                    continue
                if idx == 0:
                    # SKONTROLOVAT !!!!! chyba v skip_bitmask (zly pocet bitov)

                    skip_mask = ((1 << begin_offset) - 1) << (8 - begin_offset)
                    byte |= skip_mask
                    if byte == 0b11111111:
                        continue
                offset = (
                    self.calc_fst_zero_table()[byte] if precalc_table
                    else 8 - int((~byte) & 0b11111111).bit_length()
                )
                if offset is None:
                    raise self.byte_256_error()
                segment = begin_segment + idx
                break
            return (segment, offset)

    @classmethod
    def find_empty_space(cls, precalc_table: bool=True,
                         start_pnt: int | None=None) -> int | None:
        """
        Tries to find empty space. Return position in data.bin.
        If it doesn't find any empty space, returns None. Values for
        offset can be precalculated using precalc_table=True.
        It is also a default value. If start_pnt is set, function
        try to find next empty space to this pointer. start_pnt
        value is pointer to the data.bin file. Default pnt is None.
        """

        utils = cls._EmptySpaceUtils(cls)
        inst_len = cls.inst_len()
        if start_pnt is not None and start_pnt % inst_len != 0:
            raise ValueError("start_pointer is not aligned with the instances")

        with ExitStack() as stack:
            tomb_path = cls.path / 'data/tombstone.map'
            f = stack.enter_context(open(tomb_path, 'rb'))
            
            if tomb_path.stat().st_size == 0:
                return None
            
            mm = stack.enter_context(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ))
            mv = stack.enter_context(memoryview(mm))

            segment: int | None = None
            offset: int | None = None

            if start_pnt is not None:
                start_pnt += inst_len
            start_pnt = start_pnt // inst_len if start_pnt is not None else 0
            begin_segment = start_pnt // 8 if start_pnt is not None else 0
            begin_offset = start_pnt % 8 if start_pnt is not None else 0
            if len(mv) < 8:
                fst_q_align = len(mv)
            else:
                fst_q_align = min((begin_segment >> 8) * 8 + 8, (len(mv) >> 8) * 8)
            segment, offset = utils.smaller_blocks(
                mv, begin_segment, begin_offset, fst_q_align, precalc_table)

            q_align_start = fst_q_align if start_pnt is not None else 0
            q_align_end = (len(mv) >> 8) * 8

            if segment is not None:
                return utils.pos_constructor(segment, offset)

            # searching whole long long ints
            for int_cycle, long in enumerate(mv[q_align_start:q_align_end].cast('Q')):
                if long == 0xFFFFFFFFFFFFFFFF:
                    continue
                base = q_align_start + int_cycle * 8
                long_len = (~long & 0xFFFFFFFFFFFFFFFF).bit_length()
                rel_segment = long_len // 8
                offset = 8 - long_len % 8
                segment = base + rel_segment
                break

            if segment is not None:
                return utils.pos_constructor(segment, offset)

            tail_start = max(q_align_end, begin_segment)

            segment, offset = utils.smaller_blocks(
                mv, tail_start, begin_offset, None, precalc_table)

        return utils.pos_constructor(segment, offset)

    @classmethod
    def read_tombstone(cls) -> bytes:
        """reads tombstone file"""

        with open(cls.path / 'data/tombstone.map', 'rb') as f:
            return f.read()
    
    @classmethod
    def check_structure_sz_consistency(cls, data_size: int, tomb_size: int) -> None:
        """check consistency in size between data.bin and tombstone.map"""

        data_inst_count, mod = divmod(data_size, cls.inst_len())
        if mod != 0:
            raise OSError("size of data.bin is incosistent")
        tomb_inst_count = tomb_size * 8

        if not (data_inst_count <= tomb_inst_count):
            raise OSError(''.join((
                "structure size between data.bin and tombstone.map don't match.\n",
                f"instances in data.bin: {data_inst_count}\n",
                f"instances in tombstone.bin: equal or less than {tomb_inst_count}"
            )))


class HighBaseModel(LowBaseModel):

    @classmethod
    @cache
    def _setup_attr_struct(cls) -> tuple[
            dict[str, int], dict[str, str], dict[str, struct.Struct]
        ]:
        attr_offset = {attr: cls.get_offset(attr) for attr in cls.__slots__}
        attr_ctype = {attr: cls.get_attr_ctype(attr) for attr in cls.__slots__}
        attr_struct = {attr: struct.Struct(ctype) for attr, ctype in attr_ctype.items()}
        return attr_offset, attr_ctype, attr_struct

    def send(self) -> None:
        """send instance into database"""

        logging = _LOG_INST.get()
        data = self.getstate()

        if logging is None:
            pnt = self.find_empty_space(self.precalc_table)
            db_size = Path(self.path / 'data/data.bin').stat().st_size

            if pnt is None or db_size <= pnt:
                with open(self.path / 'data/data.bin', 'ab') as f:
                    f.write(data)
            else:
                self._write_bytes(pnt, pnt + self.inst_len(), data)

            self._set_tombstone_flag(pnt)
        else:
            entry = logging.Entry('SEND', None, None, data)
            logging(entry)

    @classmethod
    def set(cls, *args: str) -> Table:
        """
        returns Table class with primary key as dict_key and ColumnLine
        as dict_value, that contains tuple from table
        """

        mask_len, length = cls.get_mask_len(), cls.inst_len()
        attr_offset, _, attr_struct = cls._setup_attr_struct()

        if not args:
            attributes = {attr: order for order, attr in enumerate(cls.__slots__)}
        else:
            attributes = {attr: order for order, attr in enumerate(args)}

        table = Table({}, **attributes)
        with ExitStack() as stack:
            data_path = cls.path / 'data/data.bin'
            tomb_path = cls.path / 'data/tombstone.map'
            
            data_size = data_path.stat().st_size
            tomb_size = tomb_path.stat().st_size
            cls.check_structure_sz_consistency(data_size, tomb_size)
            if data_size == 0 or tomb_size == 0:
                return table
            
            data = stack.enter_context(open(data_path, 'rb'))
            tomb = stack.enter_context(open(tomb_path, 'rb'))
            mm_data = stack.enter_context(
                mmap.mmap(data.fileno(), 0, access=mmap.ACCESS_READ))
            mm_tomb = stack.enter_context(
                mmap.mmap(tomb.fileno(), 0, access=mmap.ACCESS_READ))
            mv_data = stack.enter_context(memoryview(mm_data))

            for glob_pnt in range(0, len(mm_data), length):
                if cls.is_deleted_flag(glob_pnt, mm_tomb):
                    continue

                prefix = mv_data[glob_pnt: glob_pnt + mask_len]
                id_list_params = []

                for id_attr in cls.primary_key:
                    if cls.check_none_value(prefix, id_attr):
                        raise AttributeError(
                            "key have None value, but should not have"
                        )

                    id_offset = glob_pnt + mask_len + attr_offset[id_attr]
                    id_txt = attr_struct[id_attr].unpack_from(mm_data, id_offset)[0]
                    if isinstance(id_txt, bytes):
                        id_txt = cls.sanitize(id_txt).decode('utf-8')
                    id_list_params.append(id_txt)

                list_params = RowList()
                for attr in attributes.keys():
                    if not cls.check_none_value(prefix, attr):
                        offset = glob_pnt + mask_len + attr_offset[attr]
                        txt = attr_struct[attr].unpack_from(mm_data, offset)[0]
                        if isinstance(txt, bytes):
                            txt = cls.sanitize(txt).decode('utf-8')
                    else:
                        txt = None
                    list_params.append_named(txt, attr)

                table[tuple(id_list_params)] = list_params
                del prefix
        return table

    @classmethod
    def delete(cls, expr: str) -> int:
        """
        delete in database every tuple, where condition is evaled as True.
        Returns number of deleted lines
        """

        logging = _LOG_INST.get()
        deleted_count = 0
        mask_len, length = cls.get_mask_len(), cls.inst_len()
        ast = build_AST(SJ_alg(tokenize(expr)))
        attr_offset, attr_ctype, _ = cls._setup_attr_struct()
        #vvars = [attrib for attrib in cls.__slots__ if attrib in get_values(ast)]
        vvars = [attrib for attrib in cls.__slots__ if attrib in expr]

        with ExitStack() as stack:
            data_path = cls.path / 'data/data.bin'
            tomb_path = cls.path / 'data/tombstone.map'

            data_size = data_path.stat().st_size
            tomb_size = tomb_path.stat().st_size
            cls.check_structure_sz_consistency(data_size, tomb_size)
            if data_size == 0 or tomb_size == 0:
                return deleted_count

            data = stack.enter_context(open(data_path, 'rb'))
            tomb = stack.enter_context(open(tomb_path, 'r+b'))
            mm_data = stack.enter_context(
                mmap.mmap(data.fileno(), 0, access=mmap.ACCESS_READ))
            mm_tomb = stack.enter_context(
                mmap.mmap(tomb.fileno(), 0, access=mmap.ACCESS_WRITE))
            if logging is None:
                mv_data = None
            else:
                mv_data = stack.enter_context(memoryview(mm_data))

            for glob_pnt in range(0, len(mm_data), length):
                if cls.is_deleted_flag(glob_pnt, mm_tomb):
                    continue

                mask = cls.get_bitmask_prefix(glob_pnt)
                vals: dict[str, object] = {}

                for var in vvars:
                    if not cls.check_none_value(mask, var):
                        start = glob_pnt + mask_len + attr_offset[var]
                        val, = struct.unpack_from(attr_ctype[var], mm_data, start)

                        vals[var] = (
                            cls.sanitize(val).decode('utf-8')
                            if isinstance(val, bytes) else val
                        )
                    else:
                        vals[var] = None

                if Evaluator(vals).interpret(ast):
                    if logging is None:
                        deleted_count += 1
                        inst_ord = glob_pnt // length
                        segment, offset = divmod(inst_ord, 8)
                        mm_tomb[segment] &= ~(1 << (7 - offset))
                    else:
                        assert mv_data is not None
                        old_data = mv_data[glob_pnt : glob_pnt + cls.inst_len()].tobytes()
                        entry = logging.Entry('DELETE', glob_pnt, old_data, None)
                        logging(entry)
        return deleted_count

    @classmethod
    def delete_table(cls) -> None:
        """delete whole table"""

        open(cls.path / 'data/tombstone.map', 'w').close()
        open(cls.path / 'data/data.bin', 'w').close()

    @classmethod
    def update(cls, expr: str, **attrs: str) -> int:
        """
        update every tuple in database according to the attributes in expression
        is evalved to True. If expr is set to string "True", it will
        automaticaly change every parameter and skip expression evaluation.
        It is also recomended, when whole database should be changed, cause
        evaluation of expr will be skipped. Returns number of updated lines

        EXAMPLE:\n
        ```python
        Model.update("name == 'Jozko'", height = "50.0", nickname = "'Erik'")
        Model.update("True", height = "height + 50.0", nickname = "'Erik'")
        ```
        """

        logging = _LOG_INST.get()
        update_count = 0
        skip_check = True if expr == "True" else False
        length = cls.inst_len()
        expr_ast = build_AST(SJ_alg(tokenize(expr)))

        attr_offset, attr_ctype, attr_struct = cls._setup_attr_struct()
        attr_ord = dict(zip(cls.__slots__, range(0, len(cls.__slots__))))

        compiled_attrs = {attr: build_AST(SJ_alg(tokenize(expr))) for attr, expr in attrs.items()}
        vvars = [attr for attr in cls.__slots__ if attr in get_values(expr_ast)]
        #vvars = [attr for attr in cls.__slots__ if attr in expr]
        vvars += [attr for expr in compiled_attrs.values()
                       for attr in cls.__slots__ if attr in get_values(expr)]
        #vvars += [attr for expr in compiled_attrs.values()
        #               for attr in cls.__slots__ if attr in expr]

        with ExitStack() as stack:
            data_path = cls.path / 'data/data.bin'
            tomb_path = cls.path / 'data/tombstone.map'
            data = stack.enter_context(open(data_path, 'r+b'))
            tomb = stack.enter_context(open(tomb_path, 'rb'))

            data_size = data_path.stat().st_size
            tomb_size = tomb_path.stat().st_size
            cls.check_structure_sz_consistency(data_size, tomb_size)
            if data_size == 0 and tomb_size == 0:
                return update_count

            mm_data = stack.enter_context(
                mmap.mmap(data.fileno(), 0, access=mmap.ACCESS_WRITE))
            mm_tomb = stack.enter_context(
                mmap.mmap(tomb.fileno(), 0, access=mmap.ACCESS_READ))
            mv_data = stack.enter_context(memoryview(mm_data))

            for glob_pnt in range(0, len(mm_data), length):
                if cls.is_deleted_flag(glob_pnt, mm_tomb):
                    continue

                mask = cls.get_bitmask_prefix(glob_pnt)
                mask_len = len(mask)
                vals: dict[str, object] = {}

                for var in vvars:
                    if not cls.check_none_value(mask, var):
                        start = glob_pnt + mask_len + attr_offset[var]
                        val, = struct.unpack_from(attr_ctype[var], mm_data, start)

                        vals[var] = (
                            cls.sanitize(val).decode('utf-8') if isinstance(val, bytes)
                            else val
                        )
                    else:
                        vals[var] = None

                if skip_check or Evaluator(vals).interpret(expr_ast):
                    update_count += 1

                    # params for logging
                    log_mask = mv_data[glob_pnt: glob_pnt + mask_len].tobytes()
                    log_buff = bytearray(
                        mv_data[glob_pnt + mask_len: glob_pnt + cls.inst_len()].tobytes())

                    for attr, comp_expr in compiled_attrs.items():
                        new_val = Evaluator(vals).interpret(comp_expr)
                        start = glob_pnt + mask_len + attr_offset[attr]
                        is_none = cls.check_none_value(mask, attr)

                        if new_val is None and not is_none:
                            mask = cls._flip_prefix_bit(
                                bytearray(mask), attr_ord[attr])
                            if logging is None:
                                mv_data[glob_pnt: glob_pnt + mask_len] = mask
                            else:
                                log_mask = mask

                        elif new_val is not None and not is_none:
                            if isinstance(new_val, str):
                                new_val = cls.sanitize_str(new_val).encode('utf-8')

                            if logging is None:
                                attr_struct[attr].pack_into(mm_data, start, new_val)
                            else:
                                attr_struct[attr].pack_into(
                                    log_buff, attr_offset[attr], new_val)

                        elif new_val is not None and is_none:
                            mask = cls._flip_prefix_bit(
                                bytearray(mask), attr_ord[attr])
                            if isinstance(new_val, str):
                                new_val = cls.sanitize_str(new_val).encode('utf-8')

                            if logging is None:
                                mv_data[glob_pnt: glob_pnt + mask_len] = mask
                                attr_struct[attr].pack_into(mm_data, start, new_val)
                            else:
                                log_mask = mask
                                attr_struct[attr].pack_into(
                                    log_buff, attr_offset[attr], new_val)

                    if logging is not None:
                        old_data = mv_data[glob_pnt: glob_pnt + cls.inst_len()].tobytes()
                        new_data = bytes(log_mask + log_buff)
                        entry = logging.Entry('UPDATE', glob_pnt, old_data, new_data)
                        logging(entry)

                    del log_mask
                    del log_buff
        return update_count
