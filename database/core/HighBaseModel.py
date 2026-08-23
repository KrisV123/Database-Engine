from __future__ import annotations
import struct
import mmap
from pathlib import Path
from contextlib import ExitStack

from database.custom_eval import build_ast, eval_ast
from database.wal.wal import _LOG_INST
from database.core.types import AcceptTypes
from database.core.LowBaseModel import LowBaseModel
from database.core.table import Table
from database.core.row import RowList

class HighBaseModel(LowBaseModel):

    def send(self) -> None:
        "send instance into database"

        table_schema = self.get_table_schema()
        logging = _LOG_INST.get()
        data = self.getstate()

        if logging is None:
            pnt = self.find_empty_space()
            db_size = Path(table_schema.data_path).stat().st_size

            if pnt is None or db_size <= pnt:
                with open(table_schema.data_path, 'ab') as f:
                    f.write(data)
            else:
                self._write_bytes(pnt, pnt + table_schema.inst_len, data)

            self._set_tombstone_flag(pnt)
        else:
            entry = logging.SendEntry(data)
            logging(entry)

    @classmethod
    def set(cls, *args: str) -> Table[AcceptTypes]:
        """
        returns Table class with primary key as dict_key and ColumnLine
        as dict_value, that contains tuple from table
        """

        table_schema = cls.get_table_schema()
        mask_len, length = table_schema.mask_len, table_schema.inst_len
        attr_struct_dict = table_schema.attr_struct_dict
        attr_offset_dict = table_schema.attr_offset_dict

        if args:
            attributes = {attr: order for order, attr in enumerate(args)}
        else:
            attributes = table_schema.attr_ord_dict

        table = Table({}, **attributes)
        with ExitStack() as stack:
            data_path = table_schema.data_path
            tomb_path = table_schema.tomb_path

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

                for id_attr in table_schema.primary_key:
                    if cls.check_none_value(prefix, id_attr):
                        raise AttributeError(
                            "key have None value, but should not have"
                        )

                    id_offset = glob_pnt + mask_len + attr_offset_dict[id_attr]
                    id_txt = attr_struct_dict[id_attr].unpack_from(mm_data, id_offset)[0]
                    if isinstance(id_txt, bytes):
                        id_txt = cls.sanitize(id_txt).decode('utf-8')
                    id_list_params.append(id_txt)

                list_params = RowList()
                for attr in attributes.keys():
                    if not cls.check_none_value(prefix, attr):
                        offset = glob_pnt + mask_len + attr_offset_dict[attr]
                        txt = attr_struct_dict[attr].unpack_from(mm_data, offset)[0]
                        if isinstance(txt, bytes):
                            txt = cls.sanitize(txt).decode('utf-8')
                    else:
                        txt = None
                    list_params.append_named(txt, attr)

                table[tuple(id_list_params)] = list_params
                prefix.release()
        return table

    @classmethod
    def delete(cls, expr: str) -> int:
        """
        delete in database every tuple, where condition is evalved as True.
        Returns number of deleted lines
        """

        table_schema = cls.get_table_schema()
        logging = _LOG_INST.get()
        deleted_count = 0
        length, mask_len = table_schema.inst_len, table_schema.mask_len
        attr_offset_dict = table_schema.attr_offset_dict
        attr_ctype_dict = table_schema.attr_ctype_dict
        ast = build_ast(expr)
        vvars = [attrib for attrib in table_schema.attributes if attrib in expr]

        with ExitStack() as stack:
            data_path = table_schema.data_path
            tomb_path = table_schema.tomb_path

            data_size = data_path.stat().st_size
            tomb_size = tomb_path.stat().st_size
            cls.check_structure_sz_consistency(data_size, tomb_size)
            if data_size == 0 and tomb_size == 0:
                return deleted_count

            data = stack.enter_context(open(data_path, 'rb'))
            tomb = stack.enter_context(open(tomb_path, 'r+b'))
            mm_data = stack.enter_context(
                mmap.mmap(data.fileno(), 0, access=mmap.ACCESS_READ))
            mm_tomb = stack.enter_context(
                mmap.mmap(tomb.fileno(), 0, access=mmap.ACCESS_WRITE))
            mv_data = None if logging is None else stack.enter_context(memoryview(mm_data))

            for glob_pnt in range(0, len(mm_data), length):
                if cls.is_deleted_flag(glob_pnt, mm_tomb):
                    continue

                mask = mm_data[glob_pnt: glob_pnt + mask_len]
                vals: dict[str, AcceptTypes] = {}

                for var in vvars:
                    if not cls.check_none_value(mask, var):
                        start = glob_pnt + mask_len + attr_offset_dict[var]
                        val, = struct.unpack_from(attr_ctype_dict[var], mm_data, start)

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
                        old_data = mv_data[glob_pnt : glob_pnt + length].tobytes()
                        entry = logging.DeleteEntry(glob_pnt, old_data)
                        logging(entry)
        return deleted_count

    @classmethod
    def delete_table(cls) -> None:
        "delete whole table"

        table_schema = cls.get_table_schema()
        logging = _LOG_INST.get()

        if logging:
            with open(table_schema.tomb_path, 'r+b') as tomb:
                all_flags = tomb.read()
                table_schema_bytes = table_schema.to_json().encode('utf-8')
                entry = logging.DeleteTableEntry(all_flags, table_schema_bytes)
                logging(entry)

            open(cls.path / 'data/meta.json', 'w').close()
        else:
            open(table_schema.tomb_path, 'w').close()
            open(table_schema.data_path, 'w').close()

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

        table_schema = cls.get_table_schema()
        logging = _LOG_INST.get()
        update_count = 0
        skip_check = expr == "True"
        length, mask_len = table_schema.inst_len, table_schema.mask_len
        attributes = table_schema.attributes
        expr_ast = build_ast(expr)

        attr_struct_dict = table_schema.attr_struct_dict
        attr_offset_dict = table_schema.attr_offset_dict
        attr_ord = dict(zip(attributes, range(0, len(attributes))))

        compiled_attrs = {attr: build_ast(expr) for attr, expr in attrs.items()}
        vvars = [attr for attr in attributes if attr in expr]
        vvars += [
            attr
            for expr in attrs.values()
            for attr in attributes if attr in expr
        ]

        with ExitStack() as stack:
            data_path = table_schema.data_path
            tomb_path = table_schema.tomb_path
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

                mask = mv_data[glob_pnt: glob_pnt + mask_len]
                vals: dict[str, AcceptTypes] = {}

                for var in vvars:
                    if not cls.check_none_value(mask, var):
                        start = glob_pnt + mask_len + attr_offset_dict[var]
                        val, = struct.unpack_from(table_schema.attr_ctype_dict[var], mm_data, start)

                        vals[var] = (
                            cls.sanitize(val).decode('utf-8') if isinstance(val, bytes)
                            else val
                        )
                    else:
                        vals[var] = None

                if skip_check or eval_ast(expr, expr_ast, vals):
                    update_count += 1

                    # params for logging
                    log_mask = bytearray(mv_data[glob_pnt: glob_pnt + mask_len])
                    log_buff = bytearray(
                        mv_data[glob_pnt + mask_len: glob_pnt + length].tobytes())

                    for attr, comp_expr in compiled_attrs.items():
                        new_val = eval_ast(expr, comp_expr, vals)
                        start = glob_pnt + mask_len + attr_offset_dict[attr]
                        is_none = cls.check_none_value(mask, attr)

                        if new_val is None and not is_none:
                            if logging is None:
                                cls._flip_prefix_bit(mask, attr_ord[attr])
                            else:
                                cls._flip_prefix_bit(log_mask, attr_ord[attr])

                        elif new_val is not None and not is_none:
                            if isinstance(new_val, str):
                                new_val = cls.sanitize_str(new_val).encode('utf-8')

                            if logging is None:
                                attr_struct_dict[attr].pack_into(mm_data, start, new_val)
                            else:
                                attr_struct_dict[attr].pack_into(
                                    log_buff, attr_offset_dict[attr], new_val)

                        elif new_val is not None and is_none:
                            if isinstance(new_val, str):
                                new_val = cls.sanitize_str(new_val).encode('utf-8')
                            if logging is None:
                                cls._flip_prefix_bit(mask, attr_ord[attr])
                                attr_struct_dict[attr].pack_into(mm_data, start, new_val)
                            else:
                                cls._flip_prefix_bit(log_mask, attr_ord[attr])
                                attr_struct_dict[attr].pack_into(
                                    log_buff, attr_offset_dict[attr], new_val)

                    if logging is not None:
                        old_data = mv_data[glob_pnt: glob_pnt + length].tobytes()
                        new_data = bytes(log_mask + log_buff)
                        entry = logging.UpdateEntry(glob_pnt, old_data, new_data)
                        logging(entry)

                mask.release()
        return update_count
