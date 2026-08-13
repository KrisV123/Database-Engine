from __future__ import annotations
import mmap
from pathlib import Path
from math import ceil
from functools import cache
from contextlib import ExitStack
from typing import Any, TypeVar, ClassVar

from database.tools.core.types import AcceptTypes, STRUCT_FORMAT_INFO, PLACEHOLDER
from database.tools.core.row import RowList
from database.tools.core.table_schema import TableSchema

class LowBaseModel:
    try:
        # for POSIX platforms
        _os_pg_align = os.sysconf("SC_PAGE_SIZE") #type:ignore
    except:
        # for Windows platform
        _os_pg_align = mmap.ALLOCATIONGRANULARITY #type:ignore

    path: ClassVar[Path] = Path()
    precalc_table = True # precalculate table for first zero in byte
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
                cls._table_schema = TableSchema.check_table_schema(cls, cls.path / 'data/meta.json')
            else:
                cls._table_schema = TableSchema.init_meta(cls)
            return cls._table_schema
        else:
            return cls._table_schema

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
        """change bytes into instance based on struct model from the class"""

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
    def get_bitmask_prefix(cls, offset: int) -> bytes:
        """return bytes, that represents offset"""

        bit_len = len(cls.get_table_schema().attributes)
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
    def check_none_value(cls, prefix: bytes | bytearray | memoryview, attr: str) -> bool:
        """checks if parameter have setted null value in prefix"""

        attr_ord = cls.get_table_schema().attr_ord_dict[attr]
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

        inst_len = cls.get_table_schema().inst_len
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

        inst_len = cls.get_table_schema().inst_len
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

            if segment is not None and offset is not None:
                return (segment * 8 + offset) * self._outer.get_table_schema().inst_len
            else:
                return None

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
        inst_len = cls.get_table_schema().inst_len
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
                fst_q_align = min((begin_segment >> 3) * 8 + 8, (len(mv) >> 3) * 8)
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
