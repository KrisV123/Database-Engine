from __future__ import annotations

from dataclasses import dataclass, field
from io import BufferedRandom
from database.wal.utils import IOutils
from enum import Enum

@dataclass(frozen=True, slots=True)
class Field:
    offset: int
    length: int


class Header_info:
    """
    Header metadata. First parameter is size and others are Fields.
    All params are in bytes
    """

    status = Field(0, 1)
    offset_tbl_size = Field(1, 8)

    #-----------------------------
    # 1 empty byte 
    # (for better aligmend with next fields and space for future one byte value)
    #-----------------------------

    model_name = Field(10, 40)
    logs_checksum = Field(50, 4)
    offset_tbl_checksum = Field(54, 4)

    header_size = 100
    class Status_consts(Enum):
        INIT = b'\x00'        # initialized, creating logs
        APPLYING = b'\x01'    # all logs created, applying to db (consistent log file, logging process not)
        APPLIED = b'\x02'     # all logs applied, finished (consistent state)
        ROLLBACKING = b'\x03' # rollbacking in process
        ROLLBACKED = b'\x04'  # finished rollbacking (consistent state)


@dataclass(slots=True)
class Header:
    """header attributes"""

    status: bytes = field(default_factory=lambda: b'\x00')
    """data from Header_info.status_consts"""

    offset_tbl_size: int = field(default_factory=lambda: 0)
    """8 byte unsigned integer"""

    model_name: str = field(default_factory=lambda: '')
    """
    30 reserved bytes in utf-8 encoding.
    NEEDS TO BE SETTED MANUALY thrue WAL._change header method
    cause theoretically, multiple table requests can be passed into one WAL object
    (even it is not recomended) and can't deteministicly decide.
    It's for documentation purposes of log file, if needed.
    """

    logs_checksum: int = field(default_factory=lambda: 0)
    """4 byte crc32 hash"""

    offset_tbl_checksum: int = field(default_factory=lambda: 0)
    """4 byte crc32 hash"""


@dataclass(slots=True)
class Log_file_struct:
    header: Header = field(default_factory=Header)
    log_segment: list[bytes] = field(default_factory=list)
    """
    byte buffer. Sequence of logs logs of dynamic size

    LOG STRUCTURE:\n

        1.  operator: (x01: SEND, x02: UPDATE, x03: DELETE, x04: DELETE_TABLE), SIZE: (static) 1 Byte\n
        2.  meta_exist: (x01: yes, x00: No) SIZE: (static) 1 Byte\n
        3.  meta: SIZE: (dynamic) first part is VarInt size and next up data with VarInt length if meta_exist is x01 else nothing\n
            (meta is mainly for TableSchema in meta.json, but can be used for anything extra)
        4.  old_data_exist: (x01: yes, x00: No) SIZE: (static) 1 Byte\n
        5.  old_data, SIZE: (dynamic) inst_len() in LowBaseModel if old_data_exist is x01 else nothing\n
            (
                in case TELETE_TABLE (x04), old data will contain snapshot of tombstone file
                and VarInt with snapshot as prefix.
                Structure: old_data_length (dynamic) stored as VarInt, old_data (old_data_length)
            )
        6.  new_data_exist: (x01: yes, x00: No) SIZE: (static) 1 Byte\n
        7.  new_data, SIZE: (dynamic) inst_len() in LowBaseModel if old_data_exist is x01 else nothing\n
        8.  meta_checksum, SIZE: (dynamic) 4 Bytes if meta_exist is x01 else nothing\n
        9.  old_checksum, SIZE: (dynamic) 4 Bytes if old_data_exist is x01 else nothing\n
        10. new_checksum, SIZE: (dynamic) 4 Bytes if new_data_exist is x01 else nothing\n
        11. pointer, SIZE: (dynamic) stored as VarInt\n
        12. applied (x00: No, x01: Yes), DEFAULT: x00, SIZE: (static) 1 Byte\n

    (this structure only applies for bytes in memory)
    """

    delta_offset_table: bytearray = field(default_factory=bytearray)
    """
    Trailer, byte_buffer. Sequence of VarInts that represents delta offsets of each log.
    Size of trailer is defined in header OFFSET_TABLE_SIZE
    """

    def flush_logs(self, log_f: BufferedRandom):
        log_f.seek(0, 2)
        log_f.write(b''.join(self.log_segment))
        IOutils._flush_buffered(log_f)
        self.log_segment = []
