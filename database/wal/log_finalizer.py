from __future__ import annotations

from zlib import crc32
from dataclasses import dataclass
from typing import TYPE_CHECKING

from database.wal.utils import IOutils
from database.wal.wal_format import Header_info

if TYPE_CHECKING:
    from database.wal.wal import WAL

class LogFinalizerError(Exception):
    pass

@dataclass(slots=True)
class LogFinalizer:
    """
    tools for handeling log document after executing transaction.\n
    (Helpers in __exit__ dunder method)
    """

    outer: WAL
    exc_val: BaseException | None

    status_consts = Header_info.Status_consts

    def handle_exc_exit(self):
        """stage, that handle Exception during transaction"""

        wal_inst = self.outer
        if not wal_inst.log_f.closed:
            wal_inst.log_f.close()
        if wal_inst.log_file_path.exists():
            wal_inst.log_file_path.unlink()
        raise LogFinalizerError(
            "Error occured during creating log file. Log document is deleted."
        ) from self.exc_val

    def finalize_log(self):
        """stage, that finalize log file form after handeling all records"""

        wal_inst = self.outer
        try:
            header_size = Header_info.header_size
            wal_inst.log_file_struct.flush_logs(wal_inst.log_f)

            size = wal_inst.log_f.tell()
            wal_inst.log_f.seek(header_size)
            logs_checksum = crc32(wal_inst.log_f.read(size - header_size))

            wal_inst.log_f.write(wal_inst.log_file_struct.delta_offset_table)
            offset_tbl_checksum = crc32(wal_inst.log_file_struct.delta_offset_table)

            IOutils._flush_buffered(wal_inst.log_f, wal_inst.durability)

            wal_inst._change_header(
                'logs_checksum',
                logs_checksum.to_bytes(4, 'little', signed=False)
            )
            wal_inst._change_header(
                'offset_tbl_checksum',
                offset_tbl_checksum.to_bytes(4, 'little',signed=False)
            )

            offset_tbl_len = len(wal_inst.log_file_struct.delta_offset_table)
            wal_inst._change_header(
                'offset_tbl_size',
                offset_tbl_len.to_bytes(8, 'little', signed=False)
            )
            wal_inst._change_header('status', self.status_consts.APPLYING.value)

        except Exception as e:
            if not wal_inst.log_f.closed:
                wal_inst.log_f.close()
            wal_inst.log_file_path.unlink()
            raise LogFinalizerError(
                "Error occured during finalizing log file. Log document is deleted"
            ) from e

    def apply_log(self):
        """stage, that applies all changes tracked in log file"""

        wal_inst = self.outer
        try:
            wal_inst.commit()
            wal_inst._change_header('status', self.status_consts.APPLIED.value)

        except Exception as e:
            try:
                wal_inst.rollback()
            except Exception as e:
                raise LogFinalizerError(
                    "FATAL ERROR: Error occured during rollbacking failed commit faze"
                ) from e
            raise LogFinalizerError(
                "Error occured during applying logs into the database. Applied logs were rollbacked"
            ) from e
