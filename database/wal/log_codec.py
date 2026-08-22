import mmap
from zlib import crc32
from dataclasses import dataclass
from typing import ParamSpec, Concatenate, TypeVar
from collections.abc import Callable

from database.varint import VarInt
from database.wal.wal_types import EntryPoints, Operator

@dataclass(slots=True, frozen=True)
class Log_data:
    "dataclass for storing log data in memory"

    operator: Operator
    meta_exist: bool
    meta: bytes | None
    old_data_exist: bool
    old_data: bytes | None
    new_data_exist: bool
    new_data: bytes | None
    meta_checksum: int | None
    old_checksum: int | None
    new_checksum: int | None
    db_pointer: int
    log_pnt: int
    applied: bool
    log_length: int


P = ParamSpec('P')
D = TypeVar('D')

@dataclass(slots=True, frozen=True)
class Log_serializer:
    entry: EntryPoints.Entry

    def serialize(self) -> bytes:
        if self.entry.start_pnt < 0:
            raise ValueError('start_pnt must be non-negative')
        entry = self.entry

        operator = self.operator_rule()
        meta_data_exist = self.bool_flag_rule(entry.meta)
        meta_data = self.optional(self.prefix_length_data)(entry.meta)
        old_data_exist = self.bool_flag_rule(entry.old_data)
        old_data = self.optional(self.old_data_rule)(entry.old_data, entry.operator)
        new_data_exist = self.bool_flag_rule(entry.new_data)
        new_data = self.optional(self.data_rule)(entry.new_data)

        optional_checksum_rule = self.optional(self.checksum_rule)
        meta_checksum = self.optional(self.meta_checksum_rule)(entry.meta)
        old_checksum = self.optional(self.old_checksum_rule)(entry.old_data, entry.operator)
        new_checksum = optional_checksum_rule(entry.new_data)

        start_pnt = self.start_pnt_rule()
        not_applied = b'\x00'

        return b''.join((
            operator,
            meta_data_exist, meta_data,
            old_data_exist, old_data,
            new_data_exist, new_data,
            meta_checksum, old_checksum, new_checksum,
            start_pnt, not_applied
        ))

    @classmethod
    def optional(cls,
                 rule: Callable[
                 Concatenate[bytes, P], bytes]
                ) -> Callable[Concatenate[bytes | None, P], bytes]:
        def wrapper(data: bytes | None, *args: P.args, **kwargs: P.kwargs) -> bytes:
            return b'' if data is None else rule(data, *args, **kwargs)
        return wrapper

    def operator_rule(self) -> bytes:
        return self.entry.operator.value

    @classmethod
    def bool_flag_rule(cls, data: bytes | None) -> bytes:
        return b'\x01' if data else b'\x00'

    @classmethod
    def prefix_length_data(cls, data: bytes) -> bytes:
        return VarInt.to_varint(len(data)) + data

    @classmethod
    def data_rule(cls, data: bytes) -> bytes:
        return data

    @classmethod
    def old_data_rule(cls, data: bytes, operator: Operator) -> bytes:
        if operator == Operator.DELETE_TABLE:
            return cls.prefix_length_data(data)
        else:
            return cls.data_rule(data)

    @classmethod
    def checksum_rule(cls, data: bytes) -> bytes:
        return crc32(data).to_bytes(4, 'little', signed=False)

    @classmethod
    def meta_checksum_rule(cls, meta: bytes) -> bytes:
        return cls.checksum_rule(cls.prefix_length_data(meta))

    @classmethod
    def old_checksum_rule(cls, old_data: bytes, operator: Operator) -> bytes:
        if operator == Operator.DELETE_TABLE:
            return cls.checksum_rule(cls.prefix_length_data(old_data))
        else:
            return cls.checksum_rule(old_data)

    @classmethod
    def varint_rule(cls, num: int) -> bytes:
        return VarInt.to_varint(num)

    def start_pnt_rule(self) -> bytes:
        return self.varint_rule(self.entry.start_pnt)


@dataclass(slots=True)
class Log_parser:

    _buffer: bytes | memoryview | mmap.mmap
    pnt: int
    inst_len: int

    @property
    def buffer(self):
        return self._buffer

    def parse_log(self) -> Log_data:
        """
        method to parse single log from buffer at starting point.
        Returns log informations in dictionary
        """

        begin_pnt = self.pnt

        operator = self.operaror_rule()
        meta_exist = self.bool_flag_rule()
        meta = self.prefix_length_data_rule() if meta_exist else None
        old_data_exist = self.bool_flag_rule()
        old_data = self.old_data_rule(operator, self.inst_len) if old_data_exist else None
        new_data_exist = self.bool_flag_rule()
        new_data = self.data_rule(self.inst_len) if new_data_exist else None
        meta_checksum = self.checksum_rule() if meta_exist else None
        old_checksum = self.checksum_rule() if old_data_exist else None
        new_checksum = self.checksum_rule() if new_data_exist else None
        db_pointer = self.varint_rule()
        applied = self.bool_flag_rule()
        log_length = self.log_length_rule(begin_pnt)

        return Log_data(
            operator,
            meta_exist, meta,
            old_data_exist, old_data,
            new_data_exist, new_data,
            meta_checksum, old_checksum, new_checksum,
            db_pointer, begin_pnt,
            applied, log_length
        )

    def operaror_rule(self) -> Operator:
        operator_byte = self.buffer[self.pnt].to_bytes(1, 'little', signed=False)
        operator = Operator(operator_byte)
        self.pnt += 1
        return operator

    def bool_flag_rule(self) -> bool:
        exist = bool(self.buffer[self.pnt])
        self.pnt += 1
        return exist

    def prefix_length_data_rule(self) -> bytes:
        varint_bytes = VarInt.find_fst_varint(self.buffer[self.pnt:])
        length = VarInt.to_int(varint_bytes)[0]
        self.pnt += len(varint_bytes)
        end = self.pnt + length
        data = bytes(self.buffer[self.pnt: end])
        self.pnt = end
        return data

    def data_rule(self, inst_len: int) -> bytes:
        end = self.pnt + inst_len
        data = bytes(self.buffer[self.pnt: end])
        self.pnt = end
        return data

    def old_data_rule(self, operator: Operator, inst_len: int) -> bytes:
        if operator == Operator.DELETE_TABLE:
            return self.prefix_length_data_rule()
        else:
            return self.data_rule(inst_len)

    def checksum_rule(self) -> int:
        checksum_size = 4

        end = self.pnt + checksum_size
        bytes_checksum = self.buffer[self.pnt: end]
        checksum = int.from_bytes(bytes_checksum, 'little', signed=False)
        self.pnt = end
        return checksum

    def varint_rule(self) -> int:
        varint_pnt = VarInt.find_fst_varint(self.buffer[self.pnt:])
        db_pointer = VarInt.to_int(varint_pnt)[0]
        self.pnt += len(varint_pnt)
        return db_pointer

    def log_length_rule(self, begin_pnt: int) -> int:
        log_length = self.pnt - begin_pnt
        self.pnt += 1
        return log_length
