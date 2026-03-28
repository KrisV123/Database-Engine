from __future__ import annotations
import mmap
import os
import pprint

from zlib import crc32
from contextvars import ContextVar
from pathlib import Path
from dataclasses import dataclass, field
from contextlib import ExitStack
from functools import wraps
from datetime import datetime

from io import BufferedRandom
from collections.abc import Generator, Callable, Iterable
from types import TracebackType
from typing import (
    TYPE_CHECKING, Literal, TypeVar, ParamSpec,
    Concatenate, Generic, overload
)
if TYPE_CHECKING:
    from database.tools.BaseModel import HighBaseModel

from database.tools.varint import VarInt

_LOG_INST: ContextVar[WAL | None] = ContextVar('log_inst', default=None)

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


@dataclass(frozen=True, slots=True)
class Field:
    offset: int
    length: int


class Header_info:
    """
    Header metadata. First parameter is size and others are Fields.
    All params are in bytes
    """

    header_size = 100
    status = Field(0, 1)
    offset_tbl_size = Field(1, 8)

    #-----------------------------
    # 1 empty byte 
    # (for better aligmend with next fields and space for future one byte value)
    #-----------------------------

    model_name = Field(10, 40)
    logs_checksum = Field(50, 4)
    offset_tbl_checksum = Field(54, 4)
    status_consts = {
        'INIT': b'\x00',        # initialized, creating logs
        'APPLYING': b'\x01',    # all logs created, applying to db (consistent log file, logging process not)
        'APPLIED': b'\x02',     # all logs applied, finished (consistent state)
        'ROLLBACKING': b'\x03', # rollbacking in process
        'ROLLBACKED': b'\x04'   # finished rollbacking (consistent state)
    }


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
    NEEDS TO BE SETTED MANUALY thru WAL._change header method
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

        1.  operator (x01: SEND, x02. UPDATE, x03. DELETE), SIZE: (static) 1 Byte\n
        2.  old_data_exist: (x01: yes, x00: No) SIZE: (static) 1 Byte\n
        3.  old_data, SIZE: (dynamic) inst_len() in LowBaseModel if old_data_exist is x01 else nothing\n
        4.  new_data_exist: (x01: yes, x00: No) SIZE: (static) 1 Byte\n
        5.  new_data, SIZE: (dynamic) inst_len() in LowBaseModel if old_data_exist is x01 else nothing\n
        6.  old_checksum, SIZE: (dynamic) 4 Bytes if old_data_exist is x01 else nothing\n
        7.  new_checksum, SIZE: (dynamic) 4 Bytes if new_data_exist is x01 else nothing\n
        8.  pointer, SIZE: (dynamic) stored as VarInt\n
        9.  applied (x00: No, x01: Yes), DEFAULT: x00, SIZE: (static) 1 Byte\n

    (this structure only applyes for bytes in memory)
    """

    delta_offset_table: bytearray = field(default_factory=bytearray)
    """
    Trailer, byte_buffer. Sequence of VarInts that represents delta offsets of each log.
    Size of trailer is defined in header OFFSET_TABLE_SIZE
    """

    def flush_logs(self, log_desc: BufferedRandom):
        log_desc.write(b''.join(self.log_segment))
        log_desc.flush()
        os.fsync(log_desc.fileno())
        self.log_segment = []


# type variables for WAL.decorator
P_d = ParamSpec('P_d')
R_d = TypeVar('R_d')

class WAL:
    """
    Append Only Write-Ahead-Log.\n

    Creates file that stores log about every mutation of the database.
    File stores inside folder {model_name}/data/wal_logs. Folder with log file
    will be created if does not exist.
    """

    log_group_size = 50

    try:
        # for POSIX platforms
        _os_pg_align = os.sysconf("SC_PAGE_SIZE") #type:ignore
    except:
        # for Windows platform
        _os_pg_align = mmap.ALLOCATIONGRANULARITY #type:ignore

    __slots__ = (
        'trans_name', 'model', 'db_size', 'db_full', 'empty_space_pnt',
        'log_file_struct', 'lst_offset', 'log_file_path', 'log_desc', '_old'
    )

    def __init__(self, model: type[HighBaseModel], trans_name: str):
        self.trans_name = trans_name
        self.model = model
        self.db_size = Path(model.path / 'data/data.bin').stat().st_size

        empty_space_pnt = model.find_empty_space()
        self.db_full = (
            True if empty_space_pnt is None or empty_space_pnt == self.db_size
            else False
        )
        self.empty_space_pnt: int = (
            self.db_size if empty_space_pnt is None
            else empty_space_pnt
        )

        self.log_file_struct = Log_file_struct()
        self.lst_offset = Header_info.header_size

        now = datetime.now().strftime('%y-%m-%d_%H-%M-%f')
        folder_path = Path(model.path / 'data/wal_logs')
        self.log_file_path = folder_path / f'{self.trans_name}_{now}.log'

        folder_path.mkdir(exist_ok=True)
        self.log_file_path.touch()

    @dualmethod
    def _change_header(obj: WAL | type[WAL],
                       attr: str,
                       data: bytes,
                       path: str | Path | None=None) -> None:
        """
        method, that rewrite header data based on attr inside a document.
        Can be casted on WAL object and WAL class. With object,
        it will also rewrite data inside a memory.
        When using with class, path to the log file needs to be provided
        """

        if isinstance(obj, type) and path is None:
            raise AttributeError("with class, path needs to be provided")

        field: Field = getattr(Header_info, attr)
        if field.length < len(data):
            raise ValueError("trying to write data to header larger then segment size")

        if isinstance(obj, WAL):
            path = obj.log_file_path

            match attr:
                case 'status':
                    mem_data = data
                case 'offset_tbl_size' | 'logs_checksum' | 'offset_tbl_checksum':
                    mem_data = int.from_bytes(data, 'little', signed=False)
                case 'model_name':
                    mem_data = data.decode('utf-8')
                case _:
                    raise ValueError('attribute does not exist')
            setattr(obj.log_file_struct.header, attr, mem_data)

        assert path is not None

        with open(path, 'r+b') as f:
            if len(data) < field.length:
                data += b'\x00' * (field.length - len(data))
            f.seek(field.offset)
            f.write(data)
            f.flush()
            os.fsync(f)

    @dualmethod
    def get_header(obj: WAL | type[WAL], path: Path | str | None=None) -> Header:
        """
        method, that returns Header dataclass object with filled attributes.
        Can be casted on WAL object and WAL class. With object, it will read
        data from memory to avoid reading from disk. In that case,
        path don't have to be setted.
        """ 

        if isinstance(obj, WAL):
            return obj.log_file_struct.header
        else:
            if path is None:
                raise AttributeError("with class, path needs to be provided")

        assert path is not None
        status, offset_tbl_size, model_name = b'', 0, ''
        logs_checksum, offset_tbl_checksum = 0, 0
        header_info_cls = Header_info

        with open(path, 'r+b') as f:
            for attr in Header.__slots__:
                field: Field = getattr(header_info_cls, attr)
                f.seek(field.offset)
                data = f.read(field.length)
                match attr:
                    case 'status':
                        status = data
                    case 'offset_tbl_size':
                        offset_tbl_size = int.from_bytes(data, 'little', signed=False)
                    case 'model_name':
                        model_name = data.strip(b'\x00').decode('utf-8')
                    case 'logs_checksum':
                        logs_checksum = int.from_bytes(data, 'little', signed=False)
                    case 'offset_tbl_checksum':
                        offset_tbl_checksum = int.from_bytes(data, 'little', signed=False)
                    case _:
                        raise AttributeError('attribute does not exist')
        return Header(
            status, offset_tbl_size, model_name, logs_checksum, offset_tbl_checksum)

    @dualmethod
    def _set_log_seg_checksum(obj: WAL | type[WAL],
                              log_file_buff: bytes | memoryview | mmap.mmap,
                              path: str | Path | None=None) -> int:
        """
        calculate and set log_checksum to the header of current data.
        Also returns new checksum. Function is not atomic, data have to be flushed.

        Can be used with object and also with class.
        With class, path to the log file must be provided.
        """

        log_end_pnt = len(log_file_buff) - obj.get_header(path).offset_tbl_size
        logs_hash = crc32(log_file_buff[Header_info.header_size: log_end_pnt])
        b_log_hash = logs_hash.to_bytes(4, 'little', signed=False)
        obj._change_header('logs_checksum', b_log_hash, path)
        return logs_hash

    def __enter__(self) -> WAL:
        try:
            self.log_desc = open(self.log_file_path, 'a+b')
            self.log_desc.write(b'\x00' * Header_info.header_size)
            self.log_desc.flush()
            os.fsync(self.log_desc)
        except:
            raise RuntimeError('something went wrong while initializing log file')

        self._old = _LOG_INST.set(self)
        return self

    def __exit__(self,
                 exc_type: type[BaseException] | None,
                 exc_val: BaseException | None,
                 _: TracebackType | None) -> None:
        try:
            if exc_type:
                if not self.log_desc.closed:
                    self.log_desc.close()
                if self.log_file_path.exists():
                    self.log_file_path.unlink()
                raise RuntimeError(
                    "Error occured during creating log file. Log document is deleted."
                ) from exc_val

            try:
                self.log_file_struct.flush_logs(self.log_desc)

                size = self.log_desc.tell()
                self.log_desc.seek(Header_info.header_size)
                logs_checksum = crc32(self.log_desc.read(size - Header_info.header_size))

                self.log_desc.write(self.log_file_struct.delta_offset_table)
                offset_tbl_checksum = crc32(self.log_file_struct.delta_offset_table)

                self.log_desc.flush()
                os.fsync(self.log_desc)
                self.log_desc.close()

                self._change_header(
                    'logs_checksum',
                    logs_checksum.to_bytes(4, 'little', signed=False)
                )
                self._change_header(
                    'offset_tbl_checksum',
                    offset_tbl_checksum.to_bytes(4, 'little',signed=False)
                )

                offset_tbl_len = len(self.log_file_struct.delta_offset_table)
                self._change_header(
                    'offset_tbl_size',
                    offset_tbl_len.to_bytes(8, 'little', signed=False)
                )
                self._change_header('status', Header_info.status_consts['APPLYING'])
            except Exception as e:
                if not self.log_desc.closed:
                    self.log_desc.close()
                self.log_file_path.unlink()
                raise RuntimeError(
                    "Error occured during finalizing log file. Log document is deleted"
                ) from e

            try:
                self.commit()
                self._change_header('status', Header_info.status_consts['APPLIED'])
            except Exception as e:
                try:
                    self.rollback()
                except Exception as e:
                    raise RuntimeError(
                        "FATAL ERROR: Error occured during commiting and also rollbacking"
                    ) from e
                raise RuntimeError(
                    "Error occured during applying logs into the database. Applied logs were rollbacked"
                ) from e
        finally:
            _LOG_INST.reset(self._old)

    @classmethod
    def decorator(cls, model: type[HighBaseModel], trans_name: str) -> Callable[
                                [Callable[Concatenate[WAL, P_d], R_d]], Callable[P_d, R_d]
                            ]:
        """
        recomended way to log transaction thru decorator.
        WAL instance is prefilled as first argument. Needs to be reserved for that.
        """

        def outer_dec(funct: Callable[Concatenate[WAL, P_d], R_d]) -> Callable[P_d, R_d]:
            @wraps(funct)
            def wrapper(*args: P_d.args, **kwargs: P_d.kwargs) -> R_d:
                with WAL(model, trans_name) as inst:
                    return funct(inst, *args, **kwargs)
            return wrapper
        return outer_dec

    @dataclass(slots=True)
    class Entry:
        operator: str
        start_pnt: int | None
        old_data: bytes | None
        new_data: bytes | None

    def __call__(self, entry: Entry) -> None:
        """create and write log into log file based on params"""

        self._handle_operator(entry)
        log = self.create_log(entry)
        self._handle_offsets(len(log))
        self.log_file_struct.log_segment.append(log)
        if len(self.log_file_struct.log_segment) >= self.log_group_size:
            self.log_file_struct.flush_logs(self.log_desc)

    def _handle_offsets(self, log_len: int) -> None:
        """
        helper method, that creates delta offset table.
        Internam method, not meant to be used.
        """

        varint_delta_offset = VarInt.to_varint(self.lst_offset)
        self.lst_offset = log_len
        self.log_file_struct.delta_offset_table += varint_delta_offset

    def _handle_operator(self, entry: Entry) -> None:
        """correctly setup all params for new log and logging instance based on operator"""

        match entry.operator:
            case 'SEND':
                assert entry.start_pnt is None
                assert entry.old_data is None
                assert entry.new_data is not None

                if not self.db_full:
                    entry.start_pnt = self.empty_space_pnt
                    entry.old_data = self.model.read_bytes(
                        entry.start_pnt,
                        entry.start_pnt + self.model.inst_len()
                    )
                    new_empty_space = self.model.find_empty_space(
                        start_pnt=self.empty_space_pnt
                    )
                    if (new_empty_space is None or
                        new_empty_space == self.db_size):
                        self.db_full = True
                        self.empty_space_pnt = self.db_size
                    else:
                        self.empty_space_pnt = new_empty_space
                else:
                    entry.start_pnt = self.empty_space_pnt
                    self.empty_space_pnt += self.model.inst_len()

            case 'UPDATE':
                assert entry.start_pnt is not None
                assert entry.old_data is not None
                assert entry.new_data is not None

            case 'DELETE':
                assert entry.start_pnt is not None
                assert entry.old_data is not None
                assert entry.new_data is None

                if self.db_full:
                    self.db_full = False
                    self.empty_space_pnt = entry.start_pnt
                else:
                    if entry.start_pnt < self.empty_space_pnt:
                        self.empty_space_pnt = entry.start_pnt
            case _:
                raise TypeError("operation or value for operator does not exist")

    @classmethod
    def create_log(cls, entry: Entry) -> bytes:
        """construct log byte buffer from entry object"""

        assert entry.start_pnt is not None
        assert entry.start_pnt >= 0

        byte_start_pnt = VarInt.to_varint(entry.start_pnt)

        old_checksum = (
            crc32(entry.old_data).to_bytes(4, 'little', signed=False)
            if entry.old_data is not None else b''
        )
        new_checksum = (
            crc32(entry.new_data).to_bytes(4, 'little', signed=False)
            if entry.new_data is not None else b''
        )
        match entry.operator:
            case 'SEND':
                operation_idx = b'\x01'
            case 'UPDATE':
                operation_idx = b'\x02'
            case 'DELETE':
                operation_idx = b'\x03'
            case _:
                raise TypeError("operation or value for operator does not exist")

        return b''.join((
            operation_idx,
            b'\x00' if entry.old_data is None else b'\x01',
            entry.old_data if entry.old_data is not None else b'',
            b'\x00' if entry.new_data is None else b'\x01',
            entry.new_data if entry.new_data is not None else b'',
            old_checksum, new_checksum, byte_start_pnt, b'\x00'
        ))


    @dataclass
    class Corrupt_log_data:
        """dataclass for storing corrupt log data in memory"""

        log_pnt: int


    @dataclass(frozen=True, slots=True)
    class Log_data:
        """dataclass for storing log data in memory"""

        operator: Literal['SEND', 'UPDATE', 'DELETE']
        old_data_exist: bool
        old_data: bytes | None
        new_data_exist: bool
        new_data: bytes | None
        old_checksum: int | None
        new_checksum: int | None
        db_pointer: int
        log_pnt: int
        applied: bool
        log_length: int


    @classmethod
    def parse_log(cls,
                  buffer: bytes | memoryview | mmap.mmap,
                  pnt: int,
                  model: type[HighBaseModel]) -> WAL.Log_data:
        """
        method to parse single log from buffer at starting point.
        Returns log informations in dictionary
        """

        inst_len = model.inst_len()
        checksum_size = 4
        begin_pnt = pnt

        match buffer[pnt]:
            case 1:
                operator = 'SEND'
            case 2:
                operator = 'UPDATE'
            case 3:
                operator = 'DELETE'
            case _:
                raise TypeError("operation or value for operator does not exist")
        pnt += 1

        old_data_exist = bool(buffer[pnt])
        pnt += 1

        if old_data_exist:
            end = pnt + inst_len
            old_data = bytes(buffer[pnt: end])
            pnt = end
        else:
            old_data = None

        new_data_exist = buffer[pnt]
        new_data_exist = bool(new_data_exist)
        pnt += 1

        if new_data_exist:
            end = pnt + inst_len
            new_data = bytes(buffer[pnt: end])
            pnt = end
        else:
            new_data = None

        if old_data_exist:
            end = pnt + checksum_size
            bytes_old_checksum = buffer[pnt: end]
            pnt = end
            old_checksum = int.from_bytes(bytes_old_checksum, 'little', signed=False)
        else:
            old_checksum = None

        if new_data_exist:
            end = pnt + checksum_size
            bytes_new_checksum = buffer[pnt: end]
            pnt = end
            new_checksum = int.from_bytes(bytes_new_checksum, 'little', signed=False)
        else:
            new_checksum = None

        varint_pnt = VarInt.find_fst_varint(buffer[pnt:])
        db_pointer = VarInt.to_int(varint_pnt)[0]
        pnt += len(varint_pnt)

        applied = buffer[pnt]
        pnt += 1
        applied = bool(applied)
        log_length = pnt - begin_pnt

        return WAL.Log_data(
            operator,
            old_data_exist, old_data,
            new_data_exist, new_data,
            old_checksum, new_checksum,
            db_pointer, begin_pnt,
            applied, log_length
        )

    @classmethod
    def iter_logs(cls,
                  model: type[HighBaseModel],
                  path: str | Path,
                  corrupt: bool=False) -> Generator[
                        WAL.Log_data | Corrupt_log_data,
                        None, None
                ]:
        """
        Generator that iterate log file and return Log_data dataclass
        from each log with each file. If corrupt is true, logs will be iterated thru
        offset table an if log is corrupted (can't be interpreted with iter_log),
        log will be interpreted with Corrupt_log_data dataclass

        Generator opens file and needs to be closed to release file descriptor
        """

        if isinstance(path, str):
            path = Path(path)

        with ExitStack() as stack:
            f = stack.enter_context(open(path, 'rb'))
            if path.stat().st_size != 0:
                mm = stack.enter_context(mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ))
                mv = stack.enter_context(memoryview(mm))
            else:
                return None

            offset_tbl_len = cls.get_header(path).offset_tbl_size
            if offset_tbl_len is None:
                raise ValueError('size of offset table was never set')

            if not corrupt:
                log_end_pnt = len(mv) - offset_tbl_len

                log_pnt = Header_info.header_size
                while log_pnt < log_end_pnt:
                    data = cls.parse_log(mv, log_pnt, model)
                    log_pnt += data.log_length
                    yield data
            else:
                delta_offsets = VarInt.to_int(mv[len(mm) - offset_tbl_len:])
                offsets = cls.calc_offsets_from_delta(delta_offsets)
                
                for offset in offsets:
                    try:
                        data = cls.parse_log(mv, offset, model)
                        yield data
                    except:
                        yield cls.Corrupt_log_data(offset)

    @classmethod
    def print_logs(cls, model: type[HighBaseModel],
                   path: str | Path,
                   format: bool=False) -> None:
        """print log as dictionary in log file"""

        iter_logs = cls.iter_logs(model, path)
        try:
            for log in iter_logs:
                if format:
                    pprint.pprint(log, sort_dicts=False)
                    print()
                else:
                    print(log)
        finally:
            try:
                iter_logs.close()
            except Exception:
                raise

    @dualmethod
    def commit(obj: WAL | type[WAL],
               model: type[HighBaseModel] | None=None,
               path: Path | str | None=None) -> None:
        """
        method, that reads whole current log file and applies not applied logs
        it into the database. Can by casted on WAL object and on WAL class.
        Only difference is, that it will use objects data stored in memory
        to avoid reading from disk. In that case, model and type path don't
        have to be passed as they are already stored inside an object
        """ 

        utils = obj._CommitUtils(obj)

        if isinstance(obj, WAL):
            model = obj.model
            path = obj.log_file_path
        else:
            if path is None:
                raise AttributeError("with class, path needs to be provided")
        assert path is not None and model is not None

        if isinstance(path, str):
            path = Path(path)

        with ExitStack() as stack:
            if not isinstance(obj, type):
                log_f = stack.enter_context(open(obj.log_file_path, 'r+b'))
                data_f = stack.enter_context(open(obj.model.path / 'data/data.bin', 'r+b'))
                tomb_f = stack.enter_context(open(obj.model.path / 'data/tombstone.map', 'r+b'))
                if obj.log_file_path.stat().st_size != 0:
                    log_f_mm = stack.enter_context(
                            mmap.mmap(log_f.fileno(), 0, access=mmap.ACCESS_WRITE))
                    log_f_mv = stack.enter_context(memoryview(log_f_mm))
                else:
                    return
            else:
                log_f = stack.enter_context(open(path, 'r+b'))
                data_f = stack.enter_context(open(model.path / 'data/data.bin', 'r+b'))
                tomb_f = stack.enter_context(open(model.path / 'data/tombstone.map', 'r+b'))
                if path.stat().st_size != 0:
                    log_f_mm = stack.enter_context(
                            mmap.mmap(log_f.fileno(), 0, access=mmap.ACCESS_WRITE))
                    log_f_mv = stack.enter_context(memoryview(log_f_mm))
                else:
                    return

            inst_len = model.inst_len() if isinstance(obj, type) else obj.model.inst_len()
            offset_tbl_len = obj.get_header(path).offset_tbl_size

            log_end_pnt = len(log_f_mv) - offset_tbl_len
            log_pnt = Header_info.header_size
            while log_pnt < log_end_pnt:
                data = obj.parse_log(
                    log_f_mv, log_pnt,
                    obj.model if not isinstance(obj, type) else model
                )

                if data.applied == b'\x01':
                    log_pnt += data.log_length
                    continue

                match data.operator:
                    case 'SEND':
                        utils.commit_send_log(
                            inst_len, log_pnt, data_f, tomb_f, log_f_mm, log_f.fileno(), data)
                    case 'UPDATE':
                        utils.commit_update_log(
                            inst_len, log_pnt, data_f, log_f_mm, log_f.fileno(), data)
                    case 'DELETE':
                        utils.commit_delete_log(
                            inst_len, log_pnt, tomb_f, log_f_mm, log_f.fileno(), data)
                log_pnt += data.log_length

            obj._set_log_seg_checksum(log_f_mm, path)
            log_f_mm.flush(0, Header_info.header_size)
            os.fsync(log_f.fileno())

    class _CommitUtils:
        """helper methods for commit method"""

        def __init__(self, outer: WAL | type):
            self.outer = outer

        @classmethod
        def raise_corruption(cls) -> OSError:
            raise OSError('coruption occured while writing instance')
        
        @classmethod
        def raise_missing_data(cls) -> ValueError:
            raise ValueError("log doesn't have any data to apply")

        @classmethod
        def commit_send_log(cls,
                            inst_len: int,
                            log_pnt: int,
                            data: BufferedRandom,
                            tomb: BufferedRandom,
                            log_f_mm: mmap.mmap,
                            log_f_fd: int,
                            data_struct: WAL.Log_data) -> None:
            """apply SEND log into database"""

            glob_pnt = data_struct.db_pointer
            tomb_pnt = glob_pnt // inst_len
            tomb_segment, tomb_offset = tomb_pnt // 8, tomb_pnt % 8

            tomb.seek(0, 2)
            tomb_size = tomb.tell()
            if tomb_size > tomb_segment:
                tomb.seek(tomb_segment, 0)
                flag: int = tomb.read(1)[0] | (1 << (7 - tomb_offset))
                flag_byte = flag.to_bytes(1, byteorder='little', signed=False)
            else:
                flag_byte = b'\x80'

            data.seek(glob_pnt, 0)
            tomb.seek(tomb_segment, 0)
            if data_struct.new_data is not None:
                data.write(data_struct.new_data)
            else:
                cls.raise_missing_data()
            tomb.write(flag_byte)

            data.flush()
            os.fsync(data.fileno())
            tomb.flush()
            os.fsync(tomb.fileno())

            data.seek(glob_pnt, 0)
            rewrite_data = data.read(inst_len)
            tomb.seek(tomb_segment, 0)
            rewrite_tomb = tomb.read(1)
            if (crc32(rewrite_data) == data_struct.new_checksum and
                rewrite_tomb == flag_byte):
                apply_pnt = log_pnt + data_struct.log_length - 1
                log_f_mm[apply_pnt] = 1
                log_f_mm.flush(apply_pnt, 1)
                os.fsync(log_f_fd)
            else:
                cls.raise_corruption()

        @classmethod
        def commit_update_log(cls,
                              inst_len: int,
                              log_pnt: int,
                              data: BufferedRandom,
                              log_f_mm: mmap.mmap,
                              log_f_fd: int,
                              data_struct: WAL.Log_data) -> None:
            """apply UPDATE log into database"""

            glob_pnt = data_struct.db_pointer
            data.seek(glob_pnt, 0)
            if data_struct.new_data is not None:
                data.write(data_struct.new_data)
            else:
                cls.raise_missing_data()
            data.flush()
            os.fsync(data.fileno())

            data.seek(glob_pnt, 0)
            rewrite_data = data.read(inst_len)
            if crc32(rewrite_data) == data_struct.new_checksum:
                apply_pnt = log_pnt + data_struct.log_length - 1
                log_f_mm[apply_pnt] = 1
                log_f_mm.flush(apply_pnt, 1)
                os.fsync(log_f_fd)
            else:
                cls.raise_corruption()

        @classmethod
        def commit_delete_log(cls,
                              inst_len: int,
                              log_pnt: int,
                              tomb: BufferedRandom,
                              log_f_mm: mmap.mmap,
                              log_f_fd: int,
                              data_struct: WAL.Log_data) -> None:
            """apply DELETE log into database"""

            glob_pnt = data_struct.db_pointer
            tomb_pnt = glob_pnt // inst_len
            tomb_segment, tomb_offset = tomb_pnt // 8, tomb_pnt % 8

            tomb.seek(tomb_segment, 0)
            flag: int = tomb.read(1)[0] & ~(1 << (7 - tomb_offset))
            flag_byte = flag.to_bytes(1, byteorder='little', signed=False)

            tomb.seek(tomb_segment, 0)
            tomb.write(flag_byte)
            tomb.flush()
            os.fsync(tomb.fileno())

            tomb.seek(tomb_segment, 0)
            rewrite_data = tomb.read(1)
            if rewrite_data == flag_byte:
                apply_pnt = log_pnt + data_struct.log_length - 1
                log_f_mm[apply_pnt] = 1
                log_f_mm.flush(apply_pnt, 1)
                os.fsync(log_f_fd)
            else:
                cls.raise_corruption()

    @dualmethod
    def get_delta_offset(obj: WAL | type[WAL], path: str | Path | None=None) -> list[int]:
        """iterable, that returns delta offsets from table"""

        if isinstance(obj, type):
            assert path is not None
            if isinstance(path, str):
                path = Path(path)

            log_file_len = path.stat().st_size
            offset_tbl_len = obj.get_header(path).offset_tbl_size
            start_pnt = log_file_len - offset_tbl_len

            with ExitStack() as stack:
                f = stack.enter_context(open(path, 'rb'))

                start_align = (start_pnt // obj._os_pg_align) * obj._os_pg_align
                mm = stack.enter_context(
                    mmap.mmap(f.fileno(),
                              log_file_len - start_align,
                              access=mmap.ACCESS_READ,
                              offset = start_align))
                mv = stack.enter_context(memoryview(mm))

                rel_start = start_pnt - start_align
                table = VarInt.to_int(mv[rel_start:].tobytes())
        else:
            table = VarInt.to_int(obj.log_file_struct.delta_offset_table)

        return table

    @classmethod
    def calc_offsets_from_delta(cls, delta_offset_table: Iterable[int]) -> list[int]:
        """calculate offset table from delta offset table"""

        acc = 0
        offsets = []
        for offset in delta_offset_table:
            acc += offset
            offsets.append(acc)
        return offsets

    @dualmethod
    def get_offsets(obj: WAL | type[WAL], path: str | Path | None=None) -> list[int]:
        """method, that returns list of offsets for each log"""

        if isinstance(obj, WAL):
            path = obj.log_file_path
        assert path is not None
        return obj.calc_offsets_from_delta(obj.get_delta_offset(path))

    @dataclass
    class Log_file_report:
        status: bytes
        not_applied_list: list[WAL.Log_data]
        unreadable_logs_pnt: list[int]
        corrupt_logs: bool
        corrupt_offsets: bool
        consistent: bool

    @classmethod
    def check_consistency(cls, model: type[HighBaseModel], path: str | Path) -> Log_file_report:
        """
        method that tries to check, if log file is in valid state.
        Returns Log_file_report dataclass with data about consistancy
        """

        if isinstance(path, str):
            path = Path(path)

        status_consts = Header_info.status_consts
        header = cls.get_header(path)
        status = header.status
        offset_tbl_size = header.offset_tbl_size

        report = WAL.Log_file_report(status, [], [], False, False, True)

        with ExitStack() as stack:
            if path.stat().st_size != 0:
                log_f = stack.enter_context(open(path, 'rb'))
                log_mm = stack.enter_context(mmap.mmap(log_f.fileno(), 0, access=mmap.ACCESS_READ))
                log_mv = stack.enter_context(memoryview(log_mm))
            else:
                raise OSError("log file is empty")

            logs_count = 0
            header_size = Header_info.header_size
            offset_tbl_start = len(log_mv) - offset_tbl_size
            offsets_checksum = crc32(log_mv[offset_tbl_start:])
            log_checksum = crc32(log_mv[header_size:offset_tbl_start])

            if log_checksum == header.logs_checksum:
                pnt = header_size
                while pnt < offset_tbl_start:
                    logs_count += 1
                    try:
                        data = cls.parse_log(log_mv, pnt, model)
                        if not data.applied:
                            report.not_applied_list.append(data)
                        pnt += data.log_length
                    except:
                        report.corrupt_logs = True
                        report.consistent = False
                        break
            else:
                report.corrupt_logs = True
                report.consistent = False

                if offsets_checksum == header.offset_tbl_checksum:
                    delta_offset_tbl = VarInt.to_int(log_mv[offset_tbl_start:])
                    offset_tbl = cls.calc_offsets_from_delta(delta_offset_tbl)

                    for i in range(len(offset_tbl) - 1, -1, -1):
                        logs_count += 1
                        offset = offset_tbl[i]
                        try:
                            data = cls.parse_log(log_mv, offset, model)
                            if not data.applied:
                                report.not_applied_list.append(data)
                        except:
                            report.unreadable_logs_pnt.append(offset)
            
            if offsets_checksum != header.offset_tbl_checksum:
                report.corrupt_offsets = True
                report.consistent = False
        
        if not ((status == status_consts['APPLIED'] and len(report.not_applied_list) == 0) or
                (status == status_consts['ROLLBACKED'] and len(report.not_applied_list) == logs_count)):
            report.consistent = False

        return report

    @dualmethod
    def rollback(obj: WAL | type[WAL],
                 model: type[HighBaseModel] | None=None,
                 path: str | Path | None=None) -> None:
        """in reverse order, rollback all applied logs from log file"""

        if isinstance(obj, WAL):
            model = obj.model
            path = obj.log_file_path
        else:
            if path is None:
                raise AttributeError("with class, path needs to be provided")
            path = Path(path)
        assert model is not None and path is not None

        status_consts = Header_info.status_consts
        obj._change_header('status', status_consts['ROLLBACKING'], path)

        offset_lst = obj.get_offsets(path)
        with ExitStack() as stack:
            data_path = model.path / 'data/data.bin'
            tomb_path = model.path / 'data/tombstone.map'
            log_len = path.stat().st_size
            data_len = data_path.stat().st_size
            tomb_len = tomb_path.stat().st_size

            if log_len != 0 and data_len != 0 and tomb_len != 0:
                log_f = stack.enter_context(open(path, 'r+b'))
                log_mm = stack.enter_context(
                    mmap.mmap(log_f.fileno(), 0, access=mmap.ACCESS_WRITE))
                log_mv = stack.enter_context(memoryview(log_mm))
                data_f = stack.enter_context(open(data_path, 'r+b'))
                data_mm = stack.enter_context(
                    mmap.mmap(data_f.fileno(), 0, access=mmap.ACCESS_WRITE))
                data_mv = stack.enter_context(memoryview(data_mm))
                tomb_f = stack.enter_context(open(tomb_path, 'r+b'))
                tomb_mm = stack.enter_context(
                    mmap.mmap(tomb_f.fileno(), 0, access=mmap.ACCESS_WRITE))
                tomb_mv = stack.enter_context(memoryview(tomb_mm))
            else:
                raise OSError(f"database or log file is empty, log_length: {log_len}, database_length: {data_len}")

            for i in range(len(offset_lst) - 1, -1, -1):
                data = obj.parse_log(log_mv, offset_lst[i], model)
                if data.applied == b'\x00':
                    continue
                glob_pnt = data.db_pointer
                match data.operator:
                    case'SEND':
                        if data.old_data_exist and data.old_data is not None:
                            data_mv[glob_pnt: glob_pnt + model.inst_len()] = data.old_data
                            data_mm.flush(glob_pnt, model.inst_len())
                            os.fsync(data_f.fileno())
                        else:
                            inst_ord = glob_pnt // model.inst_len()
                            segment, offfset = inst_ord // 8, inst_ord % 8
                            mask = tomb_mv[segment]
                            tomb_mv[segment] = mask & ~(1 << (7 - offfset))
                            tomb_mm.flush(segment, 1)
                            os.fsync(tomb_f.fileno())
                    case 'UPDATE':
                        if data.old_data_exist and data.old_data is not None:
                            data_mv[glob_pnt: glob_pnt + model.inst_len()] = data.old_data
                            data_mm.flush(glob_pnt, model.inst_len())
                            os.fsync(data_f.fileno())
                        else:
                            raise ValueError('something wierd happend')
                    case 'DELETE':
                        inst_ord = glob_pnt // model.inst_len()
                        segment, offfset = inst_ord // 8, inst_ord % 8
                        mask = tomb_mv[segment]
                        tomb_mv[segment] = mask | (1 << (7 - offfset))
                        tomb_mm.flush(segment, 1)
                        os.fsync(tomb_f.fileno())
                    case _:
                        raise TypeError("operation or value for operator does not exist")

                # seting log to unapplied
                log_mv[offset_lst[i] + data.log_length - 1] = 0
                log_mm.flush(offset_lst[i] + data.log_length - 1, 1)
                os.fsync(log_f.fileno())

            obj._set_log_seg_checksum(log_mv, path)
            obj._change_header('status', status_consts['ROLLBACKED'], path)
            log_mm.flush(0, Header_info.header_size)
            os.fsync(log_f.fileno())
