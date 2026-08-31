from __future__ import annotations
import mmap
import re
from pathlib import Path
from math import ceil
from contextlib import ExitStack
from typing import Any, TypeVar, ClassVar

from database.core.types import AcceptTypes, STRUCT_FORMAT_INFO, PLACEHOLDER
from database.core.row import RowList
from database.core.table_schema import TableSchema
from database.core.meta import BaseModelMeta

class LowBaseModel(metaclass=BaseModelMeta):
    _os_pg_align: ClassVar[int] = mmap.ALLOCATIONGRANULARITY

    path: ClassVar[Path]
    _table_schema: ClassVar[TableSchema | None] = None

    @classmethod
    def get_table_schema(cls) -> TableSchema:
        """
        cache precompiled model metadata, that returns in TableSchema.
        TableSchema contains ground truth data about model and derived metadata.

        TableSchema is also using lazy singleton patern to evaluate.

        In first runtime evaluation, function checks, if meta.json exists.
        If not, meta.json is created from current data.
        If yes, meta.json will be used to check, if table data are correct.
        """

        if cls._table_schema is None:
            meta_exists = (cls.path / 'data/meta.json').exists()
            try:
                meta_size = (cls.path / 'data/meta.json').stat().st_size
            except:
                meta_size = 0
            if meta_exists and meta_size == 0:
                cls._table_schema = TableSchema.init_meta(cls)
            elif meta_exists:
                cls._table_schema = TableSchema.check_table_schema(cls, cls.path)
            else:
                cls._table_schema = TableSchema.init_meta(cls)
            return cls._table_schema
        else:
            return cls._table_schema

    @staticmethod
    def sanitize(bstream: bytes) -> bytes:
        "wrapper method. Returns bstream withoud leading zero bytes"

        return bstream.rstrip(b'\x00')

    @classmethod
    def sanitize_str(cls, strg: str) -> str:
        """
        clean input from string like single question marks.
        If don't have any, behaves like echo function (identity)
        """

        return strg[1:-1] if len(strg) > 1 and strg[0] == "'" and strg[-1] == "'" else strg

    def getstate(self) -> bytes:
        "change instance into bytes"

        table_schema = self.get_table_schema()
        attrs = []
        prefix = bytearray(b'\x00' * table_schema.mask_len)
        for idx, attr in enumerate(table_schema.attributes):
            val = getattr(self, attr)

            if val is None:
                self._flip_prefix_bit(prefix, idx)
                ctype = table_schema.attr_ctype_dict[attr][-1]
                py_type = STRUCT_FORMAT_INFO[ctype]['py_type']
                plcholder = PLACEHOLDER[py_type]
                attrs.append(plcholder)
            else:
                attrs.append(val.encode('utf-8') if isinstance(val, str) else val)
        return bytes(prefix) + self.get_table_schema().packer.pack(*attrs)

    @classmethod
    def setstate(cls, bstream: bytes) -> LowBaseModel:
        "change bytes into instance based on struct model from the class"

        table_schema = cls.get_table_schema()
        prefix_len = table_schema.mask_len
        prefix = bstream[:prefix_len]
        data = table_schema.packer.unpack(bstream[prefix_len:])

        decode_data = []
        for idx, val in enumerate(data):
            if cls.check_none_value(prefix, table_schema.attributes[idx]):
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

    @classmethod
    def read_bytes(cls, start: int, end: int) -> bytes:
        "return bytes from start point to end point"

        table_schema = cls.get_table_schema()
        start_align = (start // cls._os_pg_align) * cls._os_pg_align

        with (open(table_schema.data_path, 'rb') as f,
              mmap.mmap(f.fileno(),
                        end - start_align,
                        access=mmap.ACCESS_READ,
                        offset = start_align) as mm):
            rel_start = start - start_align
            return mm[rel_start: rel_start + (end - start)]

    @classmethod
    def _write_bytes(cls, start: int, end: int, txt: bytes) -> None:
        "write bytes from start point to end point. Not recomended to use"

        table_schema = cls.get_table_schema()
        start_align = (start // cls._os_pg_align) * cls._os_pg_align

        with (open(table_schema.data_path, 'r+b') as f,
              mmap.mmap(f.fileno(),
                        end - start_align,
                        access=mmap.ACCESS_WRITE,
                        offset = start_align) as mm):
            rel_start = start - start_align
            mm[rel_start: rel_start + (end - start)] = txt

    @classmethod
    def get_bitmask_prefix(cls, offset: int) -> bytes:
        "return bytes, that represents offset"

        bit_len = len(cls.get_table_schema().attributes)
        byte_len = ceil(bit_len / 8)
        return cls.read_bytes(offset, offset + byte_len)

    @classmethod
    def _flip_prefix_bit(cls, bitmask: memoryview | bytearray, attr_ord: int) -> None:
        "mutate bitmask with flipped bit. Internal method, not meant to be used"

        segment, offset = divmod(attr_ord, 8)
        bitmask[segment] ^= (1 << (7 - offset))

    @classmethod
    def check_none_value(cls, prefix: bytes | bytearray | memoryview, attr: str) -> bool:
        "checks if parameter have setted null value in prefix"

        attr_ord = cls.get_table_schema().attr_ord_dict[attr]
        segment, offset = divmod(attr_ord, 8)
        return prefix[segment] & (1 << (7 - offset)) != 0

    @classmethod
    def is_deleted_flag(cls, pnt: int, mm: mmap.mmap) -> bool:
        """
        check if bit in tombstone is set to deleted.
        Input pnt is first byte of instance in database
        (in database, 1 means is included, 0 means missing)
        """

        if pnt < 0:
            raise IndexError("Function can't handle negative indexes")

        inst_len = cls.get_table_schema().inst_len
        if pnt % inst_len != 0:
            raise IndexError('Pointer not on start of instance')

        inst_ord = pnt // inst_len
        segment, offset = divmod(inst_ord, 8)

        if segment >= len(mm) or len(mm) == 0:
            raise IndexError('Pointer check_deleted_flag out of range')
        return (False if mm[segment] & (1 << (7 - offset)) != 0 else True)

    @classmethod
    def _set_tombstone_flag(cls, pnt: int | None) -> None:
        """
        Set bit in tombstone file to 1 (Exists). Pointer represents
        offset in data.bin. If pointer is set to None,
        it will add new byte and set bit to 1.
        Internal method, not meant to be used
        """

        table_schema = cls.get_table_schema()
        tomb_path = table_schema.tomb_path
        if pnt is None:
            with open(tomb_path, 'a+b') as f:
                f.write(bytes([1 << 7]))
        else:
            inst_len = cls.get_table_schema().inst_len
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
        "helper methods for find_empty_space method"

        fst_zero_tuple = tuple(
            None if byte == 256 else 8 - int((~byte) & 0b11111111).bit_length()
            for byte in range(256)
        )
        "lookup tuple for position of first zero bit in byte. For 255 is binded None"

        search_re = re.compile(rb'[^\xff]')

        def __init__(self, outer: type[LowBaseModel]):
            self._outer = outer

        def pos_constructor(self, segment: int | None, offset: int | None) -> int | None:
            """
            construct return value for find_empty_space method.
            Internal method, no point in using it
            """

            if segment is not None and offset is not None:
                return (segment * 8 + offset) * self._outer.get_table_schema().inst_len
            else:
                return None


    @classmethod
    def find_empty_space(cls, start_pnt: int | None=None) -> int | None:
        """
        Tries to find empty space. Return position in data.bin.
        If it doesn't find any empty space, returns None. If start_pnt is set,
        function try to find next empty space after this pointer. start_pnt
        value is pointer to the data.bin file. Default pnt is None.
        """

        table_schema = cls.get_table_schema()
        tomb_path = table_schema.tomb_path
        inst_len = table_schema.inst_len

        if start_pnt is not None and start_pnt % inst_len != 0:
            raise ValueError("start_pointer is not aligned with the instances")
        if tomb_path.stat().st_size == 0:
            return None

        utils = cls._EmptySpaceUtils(cls)
        with ExitStack() as stack:
            f = stack.enter_context(open(tomb_path, 'rb'))
            mm = stack.enter_context(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ))

            if start_pnt is None:
                byte_offset, bit_offset = 0, 0
            else:
                inst_idx = start_pnt // inst_len + 1
                byte_offset, bit_offset = inst_idx // 8, inst_idx % 8

            segment, offset = None, None

            if bit_offset:
                mask = (0xff << (8 - bit_offset)) & 0xff
                mask_val = mm[byte_offset] | mask
                if mask_val != 0xff:
                    segment = byte_offset
                    offset = utils.fst_zero_tuple[mask_val]
                else:
                    match = utils.search_re.search(mm, byte_offset + 1)
                    if match:
                        segment = match.start()
                        offset = utils.fst_zero_tuple[mm[segment]]
            else:
                match = utils.search_re.search(mm, byte_offset)
                if match:
                    segment = match.start()
                    offset = utils.fst_zero_tuple[mm[segment]]

        return utils.pos_constructor(segment, offset)

    @classmethod
    def read_tombstone(cls) -> bytes:
        "reads tombstone file"

        table_schema = cls.get_table_schema()
        with open(table_schema.tomb_path, 'rb') as f:
            return f.read()

    @classmethod
    def check_structure_sz_consistency(cls, data_size: int, tomb_size: int) -> None:
        "check consistency in size between data.bin and tombstone.map"

        data_inst_count, mod = divmod(data_size, cls.get_table_schema().inst_len)
        if mod != 0:
            raise OSError("size of data.bin is incosistent")
        tomb_inst_count = tomb_size * 8

        if not (data_inst_count <= tomb_inst_count):
            raise OSError(''.join((
                "structure size between data.bin and tombstone.map don't match.\n",
                f"instances in data.bin: {data_inst_count}\n",
                f"instances in tombstone.bin: equal or less than {tomb_inst_count}"
            )))
