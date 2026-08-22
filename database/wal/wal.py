from __future__ import annotations
import mmap
import pprint

from zlib import crc32
from contextvars import ContextVar
from pathlib import Path
from dataclasses import dataclass
from contextlib import ExitStack
from functools import wraps
from datetime import datetime

from collections.abc import Generator, Callable, Iterable
from types import TracebackType
from typing import (
    TYPE_CHECKING, TypeVar, ParamSpec, Concatenate, assert_never
)
if TYPE_CHECKING:
    from database.core.HighBaseModel import HighBaseModel

from database.varint import VarInt
from database.wal.dualmethod import dualmethod
from database.wal.utils import _RollbacUtils, _CommitUtils, IOutils
from database.wal.wal_format import Field, Header_info, Header, Log_file_struct
from database.wal.wal_types import EntryPoints, Operator
from database.wal.log_codec import Log_serializer, Log_parser, Log_data

_LOG_INST: ContextVar[WAL | None] = ContextVar('log_inst', default=None)

# type variables for WAL.decorator
P_d = ParamSpec('P_d')
R_d = TypeVar('R_d')

class WAL(EntryPoints):
    """
    Append Only Write-Ahead-Log.\n

    Tool for ensuring atomicity and integrity of transaction\n

    Creates file that stores log about every mutation of the database.
    After creating while file, changes will be applyed to database.
    File stores inside folder {model_name}/data/wal_logs. Folder with log file
    will be created, if does not exist.
    """

    log_group_size = 50
    "decides, how many log changes have to be modified to be flushed into disk. Default 50"

    durability = True
    "dicides, if data should be flushed after every IO write operation. Defalut True"

    integrity = False
    """decides, if will be checked correctness of written data. Default False"""

    if durability == False and integrity == True:
        raise Exception('Integrity can not be setted without durability')

    _mmap_align: int = mmap.ALLOCATIONGRANULARITY

    __slots__ = (
        'trans_name', 'model', 'db_size', 'db_full', 'empty_space_pnt',
        'log_file_struct', 'lst_offset', 'log_file_path', 'log_f', '_old'
    )

    def __init__(self, model: type[HighBaseModel], trans_name: str):
        table_schema = model.get_table_schema()

        self.trans_name = trans_name
        self.model = model
        self.db_size = table_schema.data_path.stat().st_size

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
        folder_path = model.path / 'data/wal_logs'
        self.log_file_path = folder_path / f'{self.trans_name}_{now}.log'

        folder_path.mkdir(exist_ok=True)
        self.log_file_path.touch()
        self.log_f = open(self.log_file_path, 'a+b')

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
            IOutils._flush_buffered(f, obj.durability)

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

        with open(path, 'rb') as f:
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
            self.log_f.write(b'\x00' * Header_info.header_size)
            IOutils._flush_buffered(self.log_f, self.durability)
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
                if not self.log_f.closed:
                    self.log_f.close()
                if self.log_file_path.exists():
                    self.log_file_path.unlink()
                raise RuntimeError(
                    "Error occured during creating log file. Log document is deleted."
                ) from exc_val

            try:
                self.log_file_struct.flush_logs(self.log_f)

                size = self.log_f.tell()
                self.log_f.seek(Header_info.header_size)
                logs_checksum = crc32(self.log_f.read(size - Header_info.header_size))

                self.log_f.write(self.log_file_struct.delta_offset_table)
                offset_tbl_checksum = crc32(self.log_file_struct.delta_offset_table)

                IOutils._flush_buffered(self.log_f, self.durability)
                self.log_f.close()

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
                if not self.log_f.closed:
                    self.log_f.close()
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
                        "FATAL ERROR: Error occured during rollbacking failed commit faze"
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
        recomended way to log transaction thrue decorator.
        WAL instance is prefilled as first argument. Needs to be reserved for that.
        """

        def outer_dec(funct: Callable[Concatenate[WAL, P_d], R_d]) -> Callable[P_d, R_d]:
            @wraps(funct)
            def wrapper(*args: P_d.args, **kwargs: P_d.kwargs) -> R_d:
                with WAL(model, trans_name) as inst:
                    return funct(inst, *args, **kwargs)
            return wrapper
        return outer_dec

    def __call__(self, entry: EntryPoints.UserEntry) -> None:
        """create and write log into log file based on params"""

        filled_entry = self._handle_operator(entry)
        log = Log_serializer(filled_entry).serialize()
        self._handle_offsets(len(log))
        self.log_file_struct.log_segment.append(log)
        if len(self.log_file_struct.log_segment) >= self.log_group_size:
            self.log_file_struct.flush_logs(self.log_f)

    def _handle_offsets(self, log_len: int) -> None:
        """
        helper method, that creates delta offset table.
        Internal method, not meant to be used.
        """

        varint_delta_offset = VarInt.to_varint(self.lst_offset)
        self.lst_offset = log_len
        self.log_file_struct.delta_offset_table += varint_delta_offset

    def _handle_operator(self, entry: EntryPoints.UserEntry) -> EntryPoints.Entry:
        "correctly setup all params of WAL for new log and logging instance based on operator"

        match entry:
            case self.SendEntry():
                start_pnt = self.empty_space_pnt
                table_schema = self.model.get_table_schema()

                if not self.db_full:
                    old_data = self.model.read_bytes(
                        start_pnt, start_pnt + table_schema.inst_len
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
                    old_data = None
                    self.empty_space_pnt += table_schema.inst_len

                return self.Entry(Operator.SEND, start_pnt, old_data, entry.new_data, None)

            case self.UpdateEntry():
                return self.Entry(Operator.UPDATE, entry.start_pnt, entry.old_data, entry.new_data, None)

            case self.DeleteEntry():
                if self.db_full:
                    self.db_full = False
                    self.empty_space_pnt = entry.start_pnt
                else:
                    if entry.start_pnt < self.empty_space_pnt:
                        self.empty_space_pnt = entry.start_pnt

                return self.Entry(Operator.DELETE, entry.start_pnt, entry.old_data, None, None)

            case self.DeleteTableEntry():
                self.db_full = False
                self.empty_space_pnt = 0

                # start_pnt is just placeholder value
                return self.Entry(Operator.DELETE_TABLE, 0, entry.old_data, None, entry.meta)

            case _:
                assert_never(entry)

    @dataclass
    class Corrupt_log_data:
        """dataclass for storing corrupt log data in memory"""

        log_pnt: int


    @classmethod
    def iter_logs(cls,
                  model: type[HighBaseModel],
                  path: Path,
                  corrupt: bool=False) -> Generator[
                        Log_data | Corrupt_log_data,
                        None, None
                ]:
        """
        Generator that iterate log file and return Log_data dataclass
        from each log with each file. If corrupt is true, logs will be iterated thrue
        offset table. If log is corrupted (can't be interpreted with iter_log),
        log will be interpreted with Corrupt_log_data dataclass

        Generator opens file and needs to be closed to release file descriptor
        """

        inst_len = model.get_table_schema().inst_len

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
                    data = Log_parser(mv, log_pnt, inst_len).parse_log()
                    log_pnt += data.log_length
                    yield data
            else:
                delta_offsets = VarInt.to_int(mv[len(mm) - offset_tbl_len:])
                offsets = cls.calc_offsets_from_delta(delta_offsets)
                
                for offset in offsets:
                    try:
                        data = Log_parser(mv, offset, inst_len).parse_log()
                        yield data
                    except:
                        yield cls.Corrupt_log_data(offset)

    @classmethod
    def print_logs(cls, model: type[HighBaseModel],
                   path: Path,
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
               path: Path | None=None) -> None:
        """
        method, that reads whole current log file and applies not applied logs
        into the database. Can by casted on WAL object and on WAL class.
        Only difference is, that it will use objects data stored in memory
        to avoid reading from disk. In that case, model and type path don't
        have to be passed as they are already stored inside an object
        """ 

        if isinstance(obj, WAL):
            if path is not None:
                raise AttributeError("with object, path should not be provided")
            model = obj.model
            path = obj.log_file_path
        else:
            if path is None:
                raise AttributeError("with class, path needs to be provided")
        assert path is not None and model is not None

        table_schema = model.get_table_schema()
        inst_len = table_schema.inst_len

        with ExitStack() as stack:
            data_f = stack.enter_context(open(table_schema.data_path, 'r+b', buffering=0))
            tomb_f = stack.enter_context(open(table_schema.tomb_path, 'r+b', buffering=0))
            log_f = stack.enter_context(open(path, 'r+b'))
            if path.stat().st_size != 0:
                log_f_mm = stack.enter_context(
                        mmap.mmap(log_f.fileno(), 0, access=mmap.ACCESS_WRITE))
                log_f_mv = stack.enter_context(memoryview(log_f_mm))
            else:
                return

            utils = _CommitUtils(
                inst_len, data_f, tomb_f, log_f_mm, obj._mmap_align,
                obj.durability, obj.integrity
            )
            offset_tbl_len = obj.get_header(path).offset_tbl_size

            log_end_pnt = len(log_f_mv) - offset_tbl_len
            log_pnt = Header_info.header_size
            while log_pnt < log_end_pnt:
                """
                data = obj.decode_log(
                    log_f_mv, log_pnt,
                    obj.model if not isinstance(obj, type) else model
                )
                """
                data = Log_parser(log_f_mv, log_pnt, inst_len).parse_log()

                if data.applied:
                    log_pnt += data.log_length
                    continue

                match data.operator:
                    case Operator.SEND:
                        utils.commit_send_log(log_pnt, data)
                    case Operator.UPDATE:
                        utils.commit_update_log(log_pnt, data)
                    case Operator.DELETE:
                        utils.commit_delete_log(log_pnt, data)
                    case Operator.DELETE_TABLE:
                        utils.commit_delete_table_log(log_pnt, data)
                log_pnt += data.log_length

            obj._set_log_seg_checksum(log_f_mm, path)
            IOutils._flush_aligned_mmap(
                log_f_mm, 0, Header_info.header_size, obj._mmap_align, obj.durability)

    @dualmethod
    def get_delta_offset(obj: WAL | type[WAL], path: Path | None=None) -> list[int]:
        "iterable, that returns delta offsets from table"

        if isinstance(obj, type):
            assert path is not None

            log_file_len = path.stat().st_size
            offset_tbl_len = obj.get_header(path).offset_tbl_size
            start_pnt = log_file_len - offset_tbl_len

            with ExitStack() as stack:
                f = stack.enter_context(open(path, 'rb'))

                start_align = (start_pnt // obj._mmap_align) * obj._mmap_align
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
        "calculate offset table from delta offset table"

        acc = 0
        return [(acc := acc + offset) for offset in delta_offset_table]

    @dualmethod
    def get_offsets(obj: WAL | type[WAL], path: Path | None=None) -> list[int]:
        "method, that returns list of offsets for each log"

        return obj.calc_offsets_from_delta(obj.get_delta_offset(path))

    @dataclass
    class Log_file_report:
        status: bytes
        not_applied_list: list[Log_data]
        unreadable_logs_pnt: list[int]
        corrupt_logs: bool
        corrupt_offsets: bool
        consistent: bool


    @classmethod
    def check_consistency(cls, model: type[HighBaseModel], path: Path) -> Log_file_report:
        """
        method that tries to check, if log file is in valid state.
        Returns Log_file_report dataclass with data about consistency
        """

        status_consts = Header_info.status_consts
        header = cls.get_header(path)
        status = header.status
        offset_tbl_size = header.offset_tbl_size
        inst_len = model.get_table_schema().inst_len

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
            log_checksum = crc32(log_mv[header_size: offset_tbl_start])

            if log_checksum == header.logs_checksum:
                pnt = header_size
                while pnt < offset_tbl_start:
                    logs_count += 1
                    try:
                        data = Log_parser(log_mv, pnt, inst_len).parse_log()
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
                            data = Log_parser(log_mv, offset, inst_len).parse_log()
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
                 path: Path | None=None) -> None:
        "in reverse order, rollback all applied logs from log file"

        if isinstance(obj, WAL):
            if path is not None:
                raise AttributeError("with object, path should not be provided")
            model = obj.model
            path = obj.log_file_path
        else:
            if path is None:
                raise AttributeError("with class, path needs to be provided")
        assert model is not None and path is not None

        status_consts = Header_info.status_consts
        obj._change_header('status', status_consts['ROLLBACKING'], path)

        offset_list = obj.get_offsets(path)
        table_schema = model.get_table_schema()

        with ExitStack() as stack:
            data_path, tomb_path = table_schema.data_path, table_schema.tomb_path
            log_len = path.stat().st_size
            data_len, tomb_len = data_path.stat().st_size, tomb_path.stat().st_size
            inst_len = table_schema.inst_len

            if log_len == 0:
                return

            log_f = stack.enter_context(open(path, 'r+b'))
            log_mm = stack.enter_context(
                mmap.mmap(log_f.fileno(), 0, access=mmap.ACCESS_WRITE))
            log_mv = stack.enter_context(memoryview(log_mm))

            if data_len != 0 and tomb_len != 0:
                data_f = stack.enter_context(open(data_path, 'r+b', buffering=0))
                data_mm = stack.enter_context(
                    mmap.mmap(data_f.fileno(), 0, access=mmap.ACCESS_WRITE))
                data_mv = stack.enter_context(memoryview(data_mm))
                tomb_f = stack.enter_context(open(tomb_path, 'r+b', buffering=0))
            else:
                raise OSError(f"database or log file is empty, log_length: {log_len}, database_length: {data_len}")

            utils = _RollbacUtils(
                inst_len, data_mm, data_mv, tomb_f,
                model.path / 'data/meta.json', obj._mmap_align,
                obj.durability, obj.integrity
            )

            for i in range(len(offset_list) - 1, -1, -1):
                data = Log_parser(log_mv, offset_list[i], inst_len).parse_log()

                if not data.applied:
                    continue

                glob_pnt = data.db_pointer
                match data.operator:
                    case Operator.SEND:
                        utils.rollback_send_log(glob_pnt, data)
                    case Operator.UPDATE:
                        utils.rollback_update_log(glob_pnt, data)
                    case Operator.DELETE:
                        utils.rollback_delete_log(glob_pnt)
                    case Operator.DELETE_TABLE:
                        utils.rollback_delete_table_log(data)

                # seting log to unapplied
                apply_log_flag_pnt = offset_list[i] + data.log_length - 1
                log_mv[apply_log_flag_pnt] = 0
                IOutils._flush_aligned_mmap(
                    log_mm, apply_log_flag_pnt, 1, obj._mmap_align, obj.durability)

            obj._set_log_seg_checksum(log_mv, path)
            obj._change_header('status', status_consts['ROLLBACKED'], path)
            IOutils._flush_aligned_mmap(
                log_mm, 0, Header_info.header_size, obj._mmap_align, obj.durability)
