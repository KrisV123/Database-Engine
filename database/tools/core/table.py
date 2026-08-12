from __future__ import annotations

from collections import defaultdict
from typing import Literal, TypeVar, overload, cast
from warnings import warn

from database.tools.custom_eval import build_ast, eval_ast
from database.tools.core.types import AcceptTypes
from database.tools.core.row import RowList

T_diff = TypeVar('T_diff', bound=AcceptTypes)
T_ident = TypeVar('T_ident', bound=AcceptTypes)
P_join = TypeVar('P_join', bound=AcceptTypes)
B_join = TypeVar('B_join', bound=AcceptTypes)

class Table[T = AcceptTypes](dict[tuple, RowList[T]]):
    """
    Class represents one table in database where dictionary key
    is primary key and value in tuple of the database represented
    with custom ColumnLine class. It's just dictionary with additional methods
    """

    T_attrs = TypeVar('T_attrs', bound=AcceptTypes)

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
        ast = build_ast(expr)
        return Table({
            key: line for key, line in self.items()
            if eval_ast(expr, ast, {var: line[var] for var in vvars})},
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
