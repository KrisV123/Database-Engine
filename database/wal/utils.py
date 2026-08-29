from __future__ import annotations
import mmap
import os
import io

from zlib import crc32
from pathlib import Path
from dataclasses import dataclass
from io import FileIO
from typing import ClassVar

from database.varint import VarInt
from database.wal.log_codec import Log_data

class IOutils:

    @staticmethod
    def _flush_aligned_mmap(mm: mmap.mmap,
                            offset: int,
                            length: int,
                            page_align: int,
                            is_allowed: bool=True) -> None:
        if not is_allowed:
            return

        align_offset = (offset // page_align) * page_align
        end_offset = offset + length
        lst_page_align = ((end_offset + page_align - 1) // page_align) * page_align
        aligned_end = lst_page_align - align_offset
        max_length = len(mm) - align_offset
        align_length = min(max_length, aligned_end)
        mm.flush(align_offset, align_length)

    @staticmethod
    def _flush_buffered(file: io.IOBase, is_allowed: bool=True) -> None:
        if not is_allowed:
            return

        file.flush()
        os.fsync(file.fileno())


@dataclass(slots=True)
class _CommitUtils:
    "helper methods for commit method"

    # params description

    """
    1. data needs to use FileIO, because database could be empty
       (mmap can not open empty file)
       also buffering have to be set for zero, otherwise integrity tests won't work
    2. tomb needs to use FileIO, because delete_table needs to use truncate
       (any other mappings could not be opened buring truncate)
    3. log_f_mv would be used only for one operation so is depecated
    """

    inst_len: int
    data_f: FileIO
    tomb_f: FileIO
    log_f_mm: mmap.mmap
    page_align: int
    durability: bool
    integrity: bool

    class CommitError(Exception):
        pass


    coruption_error: ClassVar[CommitError] = CommitError('coruption occured while writing instance')
    missing_data_error: ClassVar[CommitError] = CommitError("log doesn't have any data to apply")

    def set_log_to_applyed(self, log_pnt: int, data: Log_data) -> None:
        apply_pnt = log_pnt + data.log_length - 1
        self.log_f_mm[apply_pnt] = 1
        IOutils._flush_aligned_mmap(self.log_f_mm, apply_pnt, 1, self.page_align, self.durability)

    def commit_send_log(self, log_pnt: int, data: Log_data) -> None:
        "apply SEND log into database"

        if data.new_data is None:
            raise self.missing_data_error

        glob_pnt = data.db_pointer
        tomb_pnt = glob_pnt // self.inst_len
        tomb_segment, tomb_offset = tomb_pnt // 8, tomb_pnt % 8

        self.tomb_f.seek(0, 2)
        tomb_size = self.tomb_f.tell()
        if tomb_size > tomb_segment:
            self.tomb_f.seek(tomb_segment)
            flag: int = self.tomb_f.read(1)[0] | (1 << (7 - tomb_offset))
            flag_byte = flag.to_bytes(1, byteorder='little', signed=False)
        else:
            flag_byte = b'\x80'

        self.data_f.seek(glob_pnt)
        self.data_f.write(data.new_data)
        IOutils._flush_buffered(self.data_f, self.durability)

        self.tomb_f.seek(tomb_segment)
        self.tomb_f.write(flag_byte)
        IOutils._flush_buffered(self.tomb_f, self.durability)

        if self.integrity:
            self.data_f.seek(glob_pnt)
            rewrite_data = self.data_f.read(self.inst_len)
            self.tomb_f.seek(tomb_segment)
            rewrite_tomb = self.tomb_f.read(1)
            if crc32(rewrite_data) != data.new_checksum or rewrite_tomb != flag_byte:
                raise self.coruption_error

        self.set_log_to_applyed(log_pnt, data)
        

    def commit_update_log(self, log_pnt: int, data: Log_data) -> None:
        "apply UPDATE log into database"

        if data.new_data is None:
            raise self.missing_data_error

        glob_pnt = data.db_pointer
        self.data_f.seek(glob_pnt)

        self.data_f.write(data.new_data)
        IOutils._flush_buffered(self.data_f, self.durability)

        if self.integrity:
            self.data_f.seek(glob_pnt)
            rewrite_data = self.data_f.read(self.inst_len)
            if crc32(rewrite_data) != data.new_checksum:
                raise self.coruption_error

        self.set_log_to_applyed(log_pnt, data)
        

    def commit_delete_log(self, log_pnt: int, data: Log_data) -> None:
        "apply DELETE log into database"

        glob_pnt = data.db_pointer
        tomb_pnt = glob_pnt // self.inst_len
        tomb_segment, tomb_offset = tomb_pnt // 8, tomb_pnt % 8

        self.tomb_f.seek(tomb_segment)
        flag: int = self.tomb_f.read(1)[0] & ~(1 << (7 - tomb_offset))
        flag_byte = flag.to_bytes(1, byteorder='little', signed=False)

        self.tomb_f.seek(tomb_segment)
        self.tomb_f.write(flag_byte)
        IOutils._flush_buffered(self.tomb_f, self.durability)

        if self.integrity:
            self.tomb_f.seek(tomb_segment)
            rewrite_data = self.tomb_f.read(1)
            if rewrite_data != flag_byte:
                raise self.coruption_error

        self.set_log_to_applyed(log_pnt, data)
        

    def commit_delete_table_log(self, log_pnt: int, data: Log_data) -> None:
        "apply DELETE_TABLE log into database"

        self.tomb_f.seek(0, 2)
        tomb_size = self.tomb_f.tell()

        self.tomb_f.seek(0, 0)
        self.tomb_f.truncate(0)
        self.tomb_f.truncate(tomb_size)
        IOutils._flush_buffered(self.tomb_f, self.durability)

        if self.integrity:
            self.tomb_f.seek(0)
            tomb_data = self.tomb_f.read()
            if int.from_bytes(tomb_data) != 0:
                raise self.coruption_error

        self.set_log_to_applyed(log_pnt, data)
        


@dataclass(slots=True)
class _RollbacUtils:
    "helper methods for rollback"

    # params description

    """
    1. data is free to use everything
    2. tomb needs to use FileIO, because delete_table needs to use truncate
       (any other mappings could not be opened buring truncate)
       also buffering have to be set for zero, otherwise integrity tests won't work
    3. if meta is needed, it will be opend directly
       (meta is opend ocasionaly, is small and always needs to read everyhing)
    """

    inst_len: int
    data_mm: mmap.mmap
    data_mv: memoryview
    tomb_f: FileIO
    meta_path: Path
    page_align: int
    durability: bool
    integrity: bool

    class RollbackError(Exception):
        pass


    coruption_error: ClassVar[RollbackError] = RollbackError('coruption occured while writing rollback data')
    missing_data_error: ClassVar[RollbackError] = RollbackError("log doesn't have any data to apply")

    def rollback_send_log(self, glob_pnt: int, data: Log_data) -> None:
        "rollback SEND log from database"

        if data.old_data is not None:
            self.data_mv[glob_pnt: glob_pnt + self.inst_len] = data.old_data
            IOutils._flush_aligned_mmap(
                self.data_mm, glob_pnt, self.inst_len, self.page_align, self.durability)

            if self.integrity:
                new_old_data = self.data_mv[glob_pnt: glob_pnt + self.inst_len]
                if crc32(new_old_data) != data.old_checksum:
                    raise self.coruption_error

        else:
            inst_ord = glob_pnt // self.inst_len
            segment, offset = inst_ord // 8, inst_ord % 8

            self.tomb_f.seek(segment)
            new_mask: int = self.tomb_f.read(1)[0] & ~(1 << (7 - offset))
            flag_byte = new_mask.to_bytes(1, byteorder='little', signed=False)
            self.tomb_f.seek(segment)
            self.tomb_f.write(flag_byte)
            IOutils._flush_buffered(self.tomb_f)

            if self.integrity:
                self.tomb_f.seek(segment)
                new_mask = int.from_bytes(self.tomb_f.read(1), 'little', signed=False)
                if new_mask & (1 << (7 - offset)):
                    raise self.coruption_error

    def rollback_update_log(self, glob_pnt: int, data: Log_data) -> None:
        "rollback UPDATE log from database"

        if data.old_data is None:
            raise self.missing_data_error

        self.data_mv[glob_pnt: glob_pnt + self.inst_len] = data.old_data
        IOutils._flush_aligned_mmap(
            self.data_mm, glob_pnt, self.inst_len, self.page_align, self.durability)

        if self.integrity:
            new_old_data = self.data_mv[glob_pnt: glob_pnt + self.inst_len]
            if crc32(new_old_data) != data.old_checksum:
                raise self.coruption_error

    def rollback_delete_log(self, glob_pnt: int) -> None:
        "rollback DELETE log from database"

        inst_ord = glob_pnt // self.inst_len
        segment, offset = inst_ord // 8, inst_ord % 8

        self.tomb_f.seek(segment)
        flag: int = self.tomb_f.read(1)[0] | (1 << (7 - offset))
        flag_byte = flag.to_bytes(1, byteorder='little', signed=False)

        self.tomb_f.seek(segment)
        self.tomb_f.write(flag_byte)
        IOutils._flush_buffered(self.tomb_f, self.durability)

        if self.integrity:
            self.tomb_f.seek(segment)
            new_mask = int.from_bytes(self.tomb_f.read(1), 'little', signed=False)
            if not (new_mask & (1 << (7 - offset))):
                raise self.coruption_error

    def rollback_delete_table_log(self, data: Log_data) -> None:
        "rollback DELETE_TABLE log from database"

        if data.old_data is None or data.meta is None:
            raise self.missing_data_error

        self.tomb_f.seek(0)
        self.tomb_f.truncate(0)
        self.tomb_f.write(data.old_data)
        IOutils._flush_buffered(self.tomb_f, self.durability)

        with open(self.meta_path, 'w+b') as meta_f:
            meta_f.write(data.meta)
            IOutils._flush_buffered(meta_f, self.durability)
            if self.integrity:
                meta_f.seek(0)
                new_bytes_meta = meta_f.read()
                new_meta_checksum = crc32(
                    VarInt.to_varint(len(new_bytes_meta)) + new_bytes_meta
                )
                if new_meta_checksum != data.meta_checksum:
                    raise self.coruption_error
