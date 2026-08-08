from __future__ import annotations
import struct
import mmap
from pathlib import Path
from functools import cache
from contextlib import ExitStack

from database.tools.custom_eval import build_ast, eval_ast

from database.tools.wal_comp import _LOG_INST

from database.tools.core.types import AcceptTypes
from database.tools.core.LowBaseModel import LowBaseModel
from database.tools.core.table import Table
from database.tools.core.row import RowList

class HighBaseModel(LowBaseModel):

    @classmethod
    @cache
    def _setup_attr_struct(cls) -> tuple[
            dict[str, int], dict[str, str], dict[str, struct.Struct]
        ]:
        endianness = cls.get_endianness_symbol()

        attr_offset = {attr: cls.get_offset(attr) for attr in cls.__slots__}
        attr_ctype = {attr: cls.get_attr_ctype(attr) for attr in cls.__slots__}
        attr_struct = {attr: struct.Struct(endianness + ctype) for attr, ctype in attr_ctype.items()}
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
    def set(cls, *args: str) -> Table[AcceptTypes]:
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
        ast = build_ast(expr)
        attr_offset, attr_ctype, _ = cls._setup_attr_struct()
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
                vals: dict[str, AcceptTypes] = {}

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

                if eval_ast(expr, ast, vals):
                    deleted_count += 1
                    if logging is None:
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

        logging = _LOG_INST.get()

        if logging:
            with open(cls.path / 'data/tombstone.map', 'r+b') as tomb:
                all_flags = tomb.read()
                entry = logging.Entry('DELETE_TABLE', None, all_flags, None)
                logging(entry)
        else:
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
        expr_ast = build_ast(expr)

        attr_offset, attr_ctype, attr_struct = cls._setup_attr_struct()
        attr_ord = dict(zip(cls.__slots__, range(0, len(cls.__slots__))))

        compiled_attrs = {attr: build_ast(expr) for attr, expr in attrs.items()}
        vvars = [attr for attr in cls.__slots__ if attr in expr]
        vvars += [
            attr
            for expr in attrs.values()
            for attr in cls.__slots__ if attr in expr
        ]

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
                vals: dict[str, AcceptTypes] = {}

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

                if skip_check or eval_ast(expr, expr_ast, vals):
                    update_count += 1

                    # params for logging
                    log_mask = mv_data[glob_pnt: glob_pnt + mask_len].tobytes()
                    log_buff = bytearray(
                        mv_data[glob_pnt + mask_len: glob_pnt + cls.inst_len()].tobytes())

                    for attr, comp_expr in compiled_attrs.items():
                        new_val = eval_ast(expr, comp_expr, vals)
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
