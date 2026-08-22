import pytest
from zlib import crc32

from database.wal.wal import WAL
from database.wal.wal_types import Operator
from database.varint import VarInt

from database.wal.log_codec import Log_serializer, Log_parser, Log_data
from tests.test_database.test_model.test import Test
import tests.test_database.expect_logs as expect_logs

model_1 = Test(1, 'Jozko', 'Mrkvicka', None, None, None).getstate()
model_2 = Test(2, 'Jerdo', 'Mravec', '01.09.1939', None, None).getstate()

fake_tombstone = b'\x00\x01\x02'
inst_len = Test.get_table_schema().inst_len

test_inputs: list[tuple[WAL.Entry, bytes, Log_data]] = [
    (
        WAL.Entry(Operator.SEND, 200, None, model_1, None),
        b''.join((
            b'\x01',
            b'\x00', b'',
            b'\x00', b'',
            b'\x01', model_1,
            b'',
            b'',
            crc32(model_1).to_bytes(4, 'little', signed=False),
            b'\xc8\x01',
            b'\x00'
        )),
        Log_data(
            operator = Operator.SEND,
            meta_exist=False,
            meta=None,
            old_data_exist=False,
            old_data=None,
            new_data_exist=True,
            new_data=model_1,
            meta_checksum=None,
            old_checksum=None,
            new_checksum=crc32(model_1),
            db_pointer=200,
            log_pnt=0,
            applied=False,
            log_length=11 + inst_len
        )
    ),(
        WAL.Entry(Operator.SEND, 256, None, model_1, None),
        b''.join((
            b'\x01',
            b'\x00', b'',
            b'\x00', b'',
            b'\x01', model_1,
            b'',
            b'',
            crc32(model_1).to_bytes(4, 'little', signed=False),
            b'\x80\x02',
            b'\x00'
        )),
        Log_data(
            operator = Operator.SEND,
            meta_exist=False,
            meta=None,
            old_data_exist=False,
            old_data=None,
            new_data_exist=True,
            new_data=model_1,
            meta_checksum=None,
            old_checksum=None,
            new_checksum=crc32(model_1),
            db_pointer=256,
            log_pnt=0,
            applied=False,
            log_length=11 + inst_len
        )
    ),(
        WAL.Entry(Operator.UPDATE, 69, model_2, model_1, None),
        b''.join((
            b'\x02',
            b'\x00', b'',
            b'\x01', model_2,
            b'\x01', model_1,
            b'',
            crc32(model_2).to_bytes(4, 'little', signed=False),
            crc32(model_1).to_bytes(4, 'little', signed=False),
            b'E',
            b'\x00'
        )),
        Log_data(
            operator = Operator.UPDATE,
            meta_exist=False,
            meta=None,
            old_data_exist=True,
            old_data=model_2,
            new_data_exist=True,
            new_data=model_1,
            meta_checksum=None,
            old_checksum=crc32(model_2),
            new_checksum=crc32(model_1),
            db_pointer=69,
            log_pnt=0,
            applied=False,
            log_length=14 + 2 * inst_len
        )
    ),(
        WAL.Entry(Operator.DELETE, 67, model_2, None, None),
        b''.join((
            b'\x03',
            b'\x00', b'',
            b'\x01', model_2,
            b'\x00', b'',
            b'',
            crc32(model_2).to_bytes(4, 'little', signed=False),
            b'',
            b'C',
            b'\x00'
        )),
        Log_data(
            operator = Operator.DELETE,
            meta_exist=False,
            meta=None,
            old_data_exist=True,
            old_data=model_2,
            new_data_exist=False,
            new_data=None,
            meta_checksum=None,
            old_checksum=crc32(model_2),
            new_checksum=None,
            db_pointer=67,
            log_pnt=0,
            applied=False,
            log_length=10 + inst_len
        )
    ),(
        WAL.Entry(Operator.DELETE_TABLE, 0, fake_tombstone, None, expect_logs.encode_table_schema),
        b''.join((
            b'\x04',
            b'\x01', VarInt.to_varint(len(expect_logs.encode_table_schema)) + expect_logs.encode_table_schema,
            b'\x01', VarInt.to_varint(len(fake_tombstone)) + fake_tombstone,
            b'\x00', b'',
            crc32(VarInt.to_varint(len(expect_logs.encode_table_schema)) + expect_logs.encode_table_schema).to_bytes(4, 'little', signed=False),
            crc32(VarInt.to_varint(len(fake_tombstone)) + fake_tombstone).to_bytes(4, 'little', signed=False),
            b'',
            b'\x00'
            b'\x00'
        )),
        Log_data(
            operator = Operator.DELETE_TABLE,
            meta_exist=True,
            meta=expect_logs.encode_table_schema,
            old_data_exist=True,
            old_data=fake_tombstone,
            new_data_exist=False,
            new_data=None,
            meta_checksum=crc32(VarInt.to_varint(len(expect_logs.encode_table_schema)) + expect_logs.encode_table_schema),
            old_checksum=crc32(VarInt.to_varint(len(fake_tombstone)) + fake_tombstone),
            new_checksum=None,
            db_pointer=0,
            log_pnt=0,
            applied=False,
            log_length=183
        )
    )
]

@pytest.mark.parametrize(
    "entry, log_bytes, log_data",
    test_inputs,
    ids=[
        'send_sanity',
        'test_two_byte_idx',
        'sanity_update',
        'sanity_delete',
        'sanity_delete_table'
    ]
)
def test_log_serializer(entry: WAL.Entry, log_bytes: bytes, log_data: Log_data):
    new_log = Log_serializer(entry).serialize()
    assert len(new_log) == len(log_bytes)
    assert new_log == log_bytes


@pytest.mark.parametrize(
    "entry, log_bytes, log_data",
    test_inputs
)
def test_parse_log(entry: WAL.Entry, log_bytes: bytes, log_data: Log_data):
    new_log_data = Log_parser(log_bytes, 0, inst_len).parse_log()
    assert new_log_data == log_data
