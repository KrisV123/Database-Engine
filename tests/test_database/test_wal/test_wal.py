"""
This tests require to pass Tests_BaseModel or
there will be failed tests that may not be caused by WAL
"""

from __future__ import annotations
import os
import pytest #type:ignore[import-not-found]
import shutil

import json
from io import BufferedRandom
from contextvars import Token
from collections.abc import Generator, Callable
from pathlib import Path

from database.wal.wal import WAL, _LOG_INST, Header_info
from tests.test_database.test_model.test import Test
from database.core.row import RowList
from database.core.table import Table

from database.wal.log_finalizer import LogFinalizerError
import tests.test_database.expect_logs as expect_logs

from database.wal.log_codec import Log_data

class Test_WAL:
    trans_name = 'log_specially_made_for_testing'
    type Db_one_use_yield = tuple[list[tuple], dict[str, int]]

    @pytest.fixture
    def db_one_usage(self) -> Generator[Db_one_use_yield, None, None]:
        Test.delete_table()
        shutil.rmtree(Test.path / 'data/wal_logs', ignore_errors=True)

        list_1 = [
            (i, 'Kristian', 'Vesely', '20.01.2001', 'kris.v@gmail.com', None)
            for i in range(5)
        ]
        list_2 = [
            (i, 'Jozko', 'Mrkvicka', None, None, None)
            for i in range(5, 11)
        ]
        attrs = {
            'id': 0, 'name': 1, 'surname': 2,
            'birth_date': 3, 'email': 4, 'phone_num': 5
        }
        list_sum = list_1 + list_2

        for data in list_sum:
            Test(*data).send()

        yield list_sum, attrs

        Test.delete_table()
        shutil.rmtree(Test.path / 'data/wal_logs', ignore_errors=False)
    
    @pytest.fixture
    def clean_db(self) -> Callable[[], None]:
        def _create() -> None:
            Test.delete_table()    
            shutil.rmtree(Test.path / 'data/wal_logs', ignore_errors=True)
        return _create
    
    class Test_WAL_init:

        def test_WAL_init_sanity(self, db_one_usage: Test_WAL.Db_one_use_yield):
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                assert Test.find_empty_space() is not None
                assert log_inst.trans_name == 'log_specially_made_for_testing'
                assert log_inst.model == Test
                assert log_inst.db_size == 1188
                assert log_inst.db_full == True
                assert log_inst.empty_space_pnt == 1188
        
        def test_WAL_init_full(self, db_one_usage: Test_WAL.Db_one_use_yield):
            for i in range(11, 16):
                Test(i, 'Adam', 'Kocan', None, None, None).send()

            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                assert Test.find_empty_space() is None
                assert log_inst.db_size == 1728
                assert log_inst.db_full == True
                assert log_inst.empty_space_pnt == 1728
        
        def test_WAL_init_not_full(self, db_one_usage: Test_WAL.Db_one_use_yield):
            Test.delete('id == 5')
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                assert log_inst.db_size == 1188
                assert log_inst.db_full == False
                assert log_inst.empty_space_pnt == 540


    class Test_change_header_and_get_header:

        def test_change_header_get_header_inst(self, clean_db: Callable[[], None]):
            clean_db()
            status = b'\x08'
            offset_tbl_size = 10
            b_offset_tbl_size = (offset_tbl_size).to_bytes(8, 'little', signed=False)
            chceksum = 222222
            b_checksum = (chceksum).to_bytes(4, 'little', signed=False)
            model_name = b'Test'
            str_model_name = 'Test'

            with WAL(Test, Test_WAL.trans_name) as log_inst:
                log_inst._change_header('status', status)
                log_inst._change_header('offset_tbl_size', b_offset_tbl_size)
                log_inst._change_header('model_name', model_name)
                log_inst._change_header('logs_checksum', b_checksum)
                log_inst._change_header('offset_tbl_checksum', b_checksum)

                header = log_inst.get_header()

                assert header.status == status
                assert header.offset_tbl_size == offset_tbl_size
                assert header.model_name == str_model_name
                assert header.logs_checksum == chceksum
                assert header.offset_tbl_checksum == chceksum

                memory_header = log_inst.log_file_struct.header

                assert memory_header.status == status
                assert memory_header.offset_tbl_size == offset_tbl_size
                assert memory_header.model_name == str_model_name
                assert memory_header.logs_checksum == chceksum
                assert memory_header.offset_tbl_checksum == chceksum

            clean_db()

        def test_change_header_get_header_cls(self, clean_db: Callable[[], None]):
            clean_db()
            status = b'\x08'
            offset_tbl_size = 10
            b_offset_tbl_size = (offset_tbl_size).to_bytes(8, 'little', signed=False)
            chceksum = 222222
            b_checksum = (chceksum).to_bytes(4, 'little', signed=False)
            model_name = b'Test'
            str_model_name = 'Test'

            with WAL(Test, Test_WAL.trans_name) as log_inst:
                log_path = log_inst.log_file_path
            
            WAL._change_header('status', status, log_path)
            WAL._change_header('offset_tbl_size', b_offset_tbl_size, log_path)
            WAL._change_header('model_name', model_name, log_path)
            WAL._change_header('logs_checksum', b_checksum, log_path)
            WAL._change_header('offset_tbl_checksum', b_checksum, log_path)

            header = WAL.get_header(log_path)

            assert header.status == status
            assert header.offset_tbl_size == offset_tbl_size
            assert header.model_name == str_model_name
            assert header.logs_checksum == chceksum
            assert header.offset_tbl_checksum == chceksum
            clean_db()
        
        def test_change_header_large_data_error(self, clean_db: Callable[[], None]):
            clean_db()
            offset_tbl_size = 10
            b_offset_tbl_size = (offset_tbl_size).to_bytes(9, 'little', signed=False)
            b_model_name = ('a' * 41).encode('utf-8')

            with pytest.raises(LogFinalizerError):
                with WAL(Test, 'testing') as log_inst:
                    log_inst._change_header('offset_tbl_size', b_offset_tbl_size)
            clean_db()

            with pytest.raises(LogFinalizerError):
                with WAL(Test, 'testing') as log_inst:
                    log_inst._change_header('model_name', b_model_name)
            clean_db()
            
            b_good_model_name = ('a' * 40).encode('utf-8')
            with WAL(Test, 'testing') as log_inst:
                log_inst._change_header('model_name', b_good_model_name)
            clean_db()
        
        def test_change_header_attr_dont_exist_error(self, clean_db: Callable[[], None]):
            clean_db()

            with pytest.raises(LogFinalizerError):
                with WAL(Test, 'testing') as log_inst:
                    log_inst._change_header('adadawda', b'\x00')
            clean_db()

            with pytest.raises((AttributeError, RuntimeError)):
                with WAL(Test, 'testing') as log_inst:
                    log_path = log_inst.log_file_path
                WAL._change_header('awdawd', b'\x00', log_path)
            clean_db()
        
        def test_change_header_missing_path(self, clean_db):
            clean_db()
            with pytest.raises(WAL.WALError):
                WAL._change_header('awdawd', b'\x00')
            clean_db()
        
        def test_get_header_missing_path(self, clean_db):
            clean_db()
            with pytest.raises(WAL.WALError):
                WAL.get_header()
            clean_db()

    class Test_enter_exit:

        def test_enter_exit_LOG_INST(self, db_one_usage: Test_WAL.Db_one_use_yield):
            assert _LOG_INST.get() is None

            with WAL(Test, 'log_specially_made_for_testing'):
                assert isinstance(_LOG_INST.get(), WAL)

            assert _LOG_INST.get() is None

        def test_enter_exit_self_params(self, db_one_usage: Test_WAL.Db_one_use_yield):
            with WAL(Test, 'log_specially_made_for_testing'):
                log_inst = _LOG_INST.get()

                assert hasattr(log_inst, 'log_f')
                assert hasattr(log_inst, '_old')
                if log_inst is not None:
                    assert isinstance(log_inst.log_f, BufferedRandom)
                    assert isinstance(log_inst._old, Token)


    class Test_handle_operator:

        @pytest.fixture
        def new_bytes_data(self) -> bytes:
            return (
                b'\x1c\n\x00\x00\x00Jozko\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'  
                b'\x00\x00\x00\x00\x00Mrkvicka\x00\x00\x00\x00\x00\x00\x00'
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' 
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' 
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' 
                b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' 
                b'\x00\x00\x00\x00'
            )

        def test_handle_operator_send_sanity_full_before(
                                            self,
                                            db_one_usage: Test_WAL.Db_one_use_yield,
                                            new_bytes_data: bytes):
            entry = WAL.SendEntry(new_bytes_data)
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                new_entry = log_inst._handle_operator(entry)
                assert new_entry.old_data is None
                assert new_entry.start_pnt == 1188
                assert new_entry.old_data == None
                assert log_inst.empty_space_pnt == 1296
                assert log_inst.db_full == True

        def test_handle_operator_send_sanity_full_after(
                                            self,
                                            db_one_usage: Test_WAL.Db_one_use_yield,
                                            new_bytes_data: bytes):
            Test.delete('id == 5')
            entry = WAL.SendEntry(new_bytes_data)
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                new_entry = log_inst._handle_operator(entry)
                assert new_entry.old_data is not None
                assert new_entry.start_pnt == 540
                assert log_inst.empty_space_pnt == 1188
                assert log_inst.db_full == True

        def test_handle_operator_send_sanity_empty_after(
                                            self,
                                            db_one_usage: Test_WAL.Db_one_use_yield,
                                            new_bytes_data: bytes):
            Test.delete("id == 5 or id == 6")
            entry = WAL.SendEntry(new_bytes_data)
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                new_entry = log_inst._handle_operator(entry)
                assert new_entry.old_data is not None
                assert new_entry.start_pnt == 540
                assert log_inst.empty_space_pnt == 648
                assert log_inst.db_full == False

        def test_handle_operator_delete_full(self, db_one_usage: Test_WAL.Db_one_use_yield):
            table = Test.set()
            bytes_model = Test.from_row(table[(4,)]).getstate()
            entry = WAL.DeleteEntry(540, bytes_model)
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                assert log_inst.db_full == True
                assert log_inst.empty_space_pnt == 1188
                log_inst._handle_operator(entry)
                assert log_inst.db_full == False
                assert log_inst.empty_space_pnt == 540

        def test_handle_operator_delete_empty_1(self, db_one_usage: Test_WAL.Db_one_use_yield):
            Test.delete("id == 3")
            table = Test.set()
            bytes_model = Test.from_row(table[(4,)]).getstate()
            entry = WAL.DeleteEntry(540, bytes_model)
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                assert log_inst.db_full == False
                assert log_inst.empty_space_pnt == 324
                log_inst._handle_operator(entry)
                assert log_inst.db_full == False
                assert log_inst.empty_space_pnt == 324

        def test_handle_operator_delete_empty_2(self, db_one_usage: Test_WAL.Db_one_use_yield):
            Test.delete("id == 8")
            table = Test.set()
            bytes_model = Test.from_row(table[(4,)]).getstate()
            entry = WAL.DeleteEntry(540, bytes_model)
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                assert log_inst.db_full == False
                assert log_inst.empty_space_pnt == 864
                log_inst._handle_operator(entry)
                assert log_inst.db_full == False
                assert log_inst.empty_space_pnt == 540

        def test_handle_operator_delete_table_sanity(self,
                                                     db_one_usage: Test_WAL.Db_one_use_yield):

            entry = WAL.DeleteTableEntry(b'\00', expect_logs.encode_table_schema)
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                assert log_inst.db_full == True
                assert log_inst.empty_space_pnt != 0
                log_inst._handle_operator(entry)
                assert log_inst.db_full == False
                assert log_inst.empty_space_pnt == 0

        def test_handle_operator_delete_table_empty(self):
            entry = WAL.DeleteTableEntry(b'\x00', expect_logs.encode_table_schema)
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                assert log_inst.db_full == True
                assert log_inst.empty_space_pnt == 0
                log_inst._handle_operator(entry)
                assert log_inst.db_full == False
                assert log_inst.empty_space_pnt == 0


    class Test_iter_logs_and_parse_log:

        def test_iter_logs_and_parse_log_send_sanity(self, clean_db):
            clean_db()
            list_1 = [
                (i, 'Kristian', 'Vesely', '20.01.2001', 'kris.v@gmail.com', None)
                for i in range(5)
            ]
            list_2 = [
                (i, 'Jozko', 'Mrkvicka', None, None, None)
                for i in range(5, 11)
            ]
            list_sum = list_1 + list_2

            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                for data in list_sum:
                    Test(*data).send()
                log_path = log_inst.log_file_path

            logs = list(WAL.iter_logs(Test, log_path))
            clean_db()
            assert logs == expect_logs.expect_send_log

        def test_iter_logs_and_parse_log_update_sanity(self, clean_db):
            clean_db()
            for i in range(5):
                model = Test(
                    i,
                    'Kristian',
                    'Vesely',
                    '20.01.2001',
                    'kris.v@gmail.com',
                    None
                )
                model.send()

            for i in range(5, 11):
                model = Test(
                    i,
                    'Jozko',
                    'Mrkvicka',
                    None, None, None
                )
                model.send()
        
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                Test.update("name == 'Kristian'", name="'Kristianossss'")
                log_path = log_inst.log_file_path

            logs = list(WAL.iter_logs(Test, log_path))
            clean_db()
            assert logs == expect_logs.expect_update_log

        def test_iter_logs_and_parse_log_delete_sanity(self, clean_db):
            clean_db()
            for i in range(5):
                model = Test(
                    i,
                    'Kristian',
                    'Vesely',
                    '20.01.2001',
                    'kris.v@gmail.com',
                    None
                )
                model.send()

            for i in range(5, 11):
                model = Test(
                    i,
                    'Jozko',
                    'Mrkvicka',
                    None, None, None
                )
                model.send()
        
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                Test.delete("id % 2 == 0")
                log_path = log_inst.log_file_path

            logs = list(WAL.iter_logs(Test, log_path))
            clean_db()
            assert logs == expect_logs.expect_delete_log

        def test_iter_logs_and_parse_log_delete_table_sanity(self, clean_db):
            clean_db()
            for i in range(5):
                model = Test(
                    i,
                    'Kristian',
                    'Vesely',
                    '20.01.2001',
                    'kris.v@gmail.com',
                    None
                )
                model.send()

            for i in range(5, 11):
                model = Test(
                    i,
                    'Jozko',
                    'Mrkvicka',
                    None, None, None
                )
                model.send()

            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                Test.delete_table()
                log_path = log_inst.log_file_path

            logs = list(WAL.iter_logs(Test, log_path))
            clean_db()
            assert logs == expect_logs.expect_delete_table_log


    class Test_commit:

        @classmethod
        def check_apply_flag(cls, log_path: Path):
            log_list = list(WAL.iter_logs(Test, log_path))
            for log in log_list:
                if log is not None:
                    assert isinstance(log, Log_data)
                    assert log.applied == True

        def test_commit_send_without_log_eq(self, clean_db: Callable[[], None]):
            clean_db()
            for i in range(10):
                Test(i, 'Kristian', 'Vesely').send()

            for i in range(10, 100):
                model = Test(
                    i, 'Jozko', 'Mrkvicka', '01.09.1939',
                    'jozko.mrkvicka@gmail.com', '0955_547_544'
                )
                model.send()

            engine_table = Test.set()
            clean_db()

            with WAL(Test, 'log_specially_made_for_testing_1'):
                for i in range(10):
                    Test(i, 'Kristian', 'Vesely').send()

            with WAL(Test, 'log_specially_made_for_testing_2'):
                for i in range(10, 100):
                    model = Test(
                        i, 'Jozko', 'Mrkvicka', '01.09.1939',
                        'jozko.mrkvicka@gmail.com', '0955_547_544'
                    )
                    model.send()

            wal_table = Test.set()
            assert engine_table == wal_table
            clean_db()

        def test_commit_send_extend(self, db_one_usage: Test_WAL.Db_one_use_yield):
            preset_data, expect_attrs = db_one_usage
            data_list = [
                (50, 'Jozko', 'Mrkvicka', None, None, None),
                (51, 'Jozko', 'Mrkvicka', None, None, None),
                (52, 'Jozko', 'Mrkvicka', None, None, None)
            ]

            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                for data in data_list:
                    Test(*data).send()
                log_path = log_inst.log_file_path

            expect_table = Table(
                {
                    (data[0],): RowList(data, **expect_attrs) 
                    for data in preset_data + data_list
                },
                **expect_attrs
            )

            assert Test.set() == expect_table
            Test_WAL.Test_commit.check_apply_flag(log_path)

        def test_commit_update(self, db_one_usage: Test_WAL.Db_one_use_yield):
            preset_data, expect_attrs = db_one_usage

            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                Test.update("name == 'Kristian'", name="'Adam'")
                log_path = log_inst.log_file_path

            expect_table = Table(
                {
                    (data[0],): RowList(
                            [data[0], 'Adam', *data[2:]] if data[1] == 'Kristian' else data,
                            **expect_attrs
                        )
                    for data in preset_data
                },
                **expect_attrs
            )

            assert Test.set() == expect_table
            Test_WAL.Test_commit.check_apply_flag(log_path)

        def test_commit_delete_1(self, db_one_usage: Test_WAL.Db_one_use_yield):
            preset_data, expect_attrs = db_one_usage
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                Test.delete("name == 'Jozko'")
                log_path = log_inst.log_file_path

            expect_table = Table(
                {
                    (data[0],): RowList(data, **expect_attrs)
                    for data in preset_data if data[1] != 'Jozko'
                },
                **expect_attrs
            )

            assert Test.set() == expect_table
            Test_WAL.Test_commit.check_apply_flag(log_path)

        def test_commit_delete_2(self, clean_db: Callable[[], None]):
            clean_db()
            for i in range(5):
                Test(i, 'Kristian', 'Vesely', None, None).send()

            for i in range(5, 10):
                model = Test(
                    i, 'Jozko', 'Mrkvicka',
                    'j.mrkvicka@gmail.com', None, None
                )
                model.send()

            Test.delete('id % 2 == 0')
            table = Test.set()

            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                Test.delete("name == 'Kristian'")
                log_path = log_inst.log_file_path

            expect_table = Table(
                {
                    (line['id'],): RowList(line, **line.attributes)
                    for line in table.values() if line['name'] != 'Kristian'
                },
                **table.attributes
            )

            assert Test.set() == expect_table
            Test_WAL.Test_commit.check_apply_flag(log_path)
            clean_db()

        def test_commit_empty(self, db_one_usage: Test_WAL.Db_one_use_yield):
            table = Test.set()
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                log_path = log_inst.log_file_path

            assert table == Test.set()

            log_list = list(WAL.iter_logs(Test, log_path))
            assert len(log_list) == 0

        def test_commit_delete_table(self, db_one_usage: Test_WAL.Db_one_use_yield):
            assert len(Test.set()) != 0

            with WAL(Test, 'log_specially_made_for_testing'):
                Test.delete_table()

            assert len(Test.set()) == 0

        def test_commit_with_class_1(self, clean_db: Callable[[], None]):
            clean_db()
            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                log_path = log_inst.log_file_path
                for i in range(10):
                    Test(i, 'Janko', 'Hrasko').send()

            Test.delete_table()
            assert len(Test.set()) == 0

            WAL.commit(Test, log_path)
            assert len(Test.set()) == 0
            clean_db()

        def test_commit_with_class_2(self, db_one_usage: Test_WAL.Db_one_use_yield):
            """Expects that rollback is working properly"""

            init_table = Test.set()

            with WAL(Test, 'log_specially_made_for_testing') as log_inst:
                log_path = log_inst.log_file_path
                for i in range(10):
                    Test(i, 'Janko', 'Hrasko').send()            
            expect_table = Test.set()

            WAL.rollback(Test, log_path)
            assert Test.set() == init_table

            WAL.commit(Test, log_path)
            assert Test.set() == expect_table


    class Test_get_delta_offset:

        def test_get_delta_offset_sanity(self, clean_db: Callable[[], None]):
            clean_db()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                for i in range(50):
                    Test(i, 'Andrej', 'Mesko').send()
                log_path = log_inst.log_file_path

            expect_delta_offsets = []
            lst_delta_offset = Header_info.header_size
            for log in list(WAL.iter_logs(Test, log_path)):
                assert log is not None
                expect_delta_offsets.append(lst_delta_offset)
                assert isinstance(log, Log_data)
                lst_delta_offset = log.log_length

            delta_offsets = list(WAL.get_delta_offset(log_path))
            assert expect_delta_offsets == delta_offsets
            clean_db()

        def test_get_delta_offset_single_offset(self, clean_db: Callable[[], None]):
            clean_db()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                for i in range(1):
                    Test(i, 'Adam', 'Kocan').send()
                log_path = log_inst.log_file_path

            delta_offsets = list(WAL.get_delta_offset(log_path))
            assert [100] == delta_offsets
            clean_db()

        def test_get_delta_offset_empty_log(self, clean_db: Callable[[], None]):
            clean_db()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                log_path = log_inst.log_file_path
            delta_offsets = list(WAL.get_delta_offset(log_path))
            assert [] == delta_offsets
            clean_db()


    class Test_get_offset:

        def test_get_offset_sanity(self, clean_db: Callable[[], None]):
            clean_db()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                for i in range(50):
                    Test(i, 'Andrej', 'Mesko').send()
                log_path = log_inst.log_file_path

            expect_offsets = []
            lst_offset = Header_info.header_size
            for log in list(WAL.iter_logs(Test, log_path)):
                assert log is not None
                expect_offsets.append(lst_offset)
                assert isinstance(log, Log_data)
                lst_offset += log.log_length

            offsets = WAL.get_offsets(log_path)
            assert expect_offsets == offsets
            clean_db()

        def test_get_offset_single_offset(self, clean_db: Callable[[], None]):
            clean_db()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                for i in range(1):
                    Test(i, 'Adam', 'Kocan').send()
                log_path = log_inst.log_file_path

            delta_offsets = WAL.get_offsets(log_path)
            assert [100] == delta_offsets
            clean_db()

        def test_get_offset_empty_log(self, clean_db: Callable[[], None]):
            clean_db()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                log_path = log_inst.log_file_path
            delta_offsets = list(WAL.get_delta_offset(log_path))
            assert [] == delta_offsets
            clean_db()
        
        def test_get_offsets_with_instance(self, clean_db: Callable[[], None]):
            clean_db()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                log_path = log_inst.log_file_path
                for i in range(5):
                    Test(i, 'Janko', 'Hrasko').send()
                inst_offsets = log_inst.get_offsets()
            class_offsets = WAL.get_offsets(log_path)
            assert class_offsets == inst_offsets
            clean_db()


    class Test_check_consistency:

        @pytest.fixture
        def setup_db_with_wal(self):
            def _create() -> Path:
                with WAL(Test, Test_WAL.trans_name) as log_inst:
                    for i in range(20, 30):
                        Test(i, 'Janko', 'Hrasko').send()
                    log_path = log_inst.log_file_path
                return log_path
            return _create

        def test_check_consistency_not_applyed_logs(
                                        self,
                                        setup_db_with_wal: Callable[[], Path],
                                        db_one_usage: Test_WAL.Db_one_use_yield):
            log_path = setup_db_with_wal()
            offsets = WAL.get_offsets(log_path)
            with open(log_path, 'r+b') as log:
                log.seek(offsets[3] - 1)
                log.write(b'\x00')
                log.seek(offsets[5] - 1)
                log.write(b'\x00')          
            report = WAL.check_consistency(Test, log_path)

            assert report.status == Header_info.Status_consts.APPLIED
            assert len(report.not_applied_list) == 2
            assert report.corrupt_logs == True
            assert report.corrupt_offsets == False
            assert len(report.unreadable_logs_pnt) == 0
            assert report.consistent == False

        def test_check_consistency_wrong_status(
                                    self,
                                    setup_db_with_wal: Callable[[], Path],
                                    db_one_usage: Test_WAL.Db_one_use_yield):
            log_path = setup_db_with_wal()
            with open(log_path, 'r+b') as log:
                log.write(b'\x01')
            report = WAL.check_consistency(Test, log_path)

            assert report.status == Header_info.Status_consts.APPLYING
            assert len(report.not_applied_list) == 0
            assert report.corrupt_logs == False
            assert report.corrupt_offsets == False
            assert len(report.unreadable_logs_pnt) == 0
            assert report.consistent == False
        
        def test_check_consistency_corrupt_offsets(
                                    self,
                                    setup_db_with_wal: Callable[[], Path],
                                    db_one_usage: Test_WAL.Db_one_use_yield):
            log_path = setup_db_with_wal()
            with open(log_path, 'r+b') as log:
                log.seek(-1, 2)
                log.write(b'\x59')
            report = WAL.check_consistency(Test, log_path)

            assert report.status == Header_info.Status_consts.APPLIED
            assert len(report.not_applied_list) == 0
            assert report.corrupt_logs == False
            assert report.corrupt_offsets == True
            assert len(report.unreadable_logs_pnt) == 0
            assert report.consistent == False

        def test_check_consistency_corrupt_data(
                                    self,
                                    setup_db_with_wal: Callable[[], Path],
                                    db_one_usage: Test_WAL.Db_one_use_yield):
            log_path = setup_db_with_wal()
            with open(log_path, 'r+b') as log:
                log.seek(120)
                log.write(b'f' * 300)
            report = WAL.check_consistency(Test, log_path)

            assert report.status == Header_info.Status_consts.APPLIED
            assert len(report.not_applied_list) == 0
            assert report.corrupt_logs == True
            assert report.corrupt_offsets == False
            assert len(report.unreadable_logs_pnt) == 2
            assert report.consistent == False

        def test_check_consistency_rollbacked(
                                    self,
                                    setup_db_with_wal: Callable[[], Path],
                                    db_one_usage: Test_WAL.Db_one_use_yield):
            log_path = setup_db_with_wal()
            WAL.rollback(Test, log_path)
            report = WAL.check_consistency(Test, log_path)

            assert report.status == Header_info.Status_consts.ROLLBACKED
            assert len(report.not_applied_list) == 10
            assert report.corrupt_logs == False
            assert report.corrupt_offsets == False
            assert len(report.unreadable_logs_pnt) == 0
            assert report.consistent == True

        def test_check_consistancy_correct_log(
                                    self,
                                    setup_db_with_wal: Callable[[], Path],
                                    db_one_usage: Test_WAL.Db_one_use_yield):
            log_path = setup_db_with_wal()
            report = WAL.check_consistency(Test, log_path)

            assert report.status == Header_info.Status_consts.APPLIED
            assert len(report.not_applied_list) == 0
            assert report.corrupt_logs == False
            assert report.corrupt_offsets == False
            assert len(report.unreadable_logs_pnt) == 0
            assert report.consistent == True


    class Test_rollback:

        def test_rollback_sanity_1(self, db_one_usage: Test_WAL.Db_one_use_yield):
            init_table = Test.set()
            new_data = [(i, 'Jozko', 'Mrkvicka', None, None, None) for i in range(20, 25)]
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                for column in new_data:
                    Test(*column).send()
                log_path = log_inst.log_file_path

            data, attrs = db_one_usage
            expect_table = Table(
                {(column[0],): RowList(column, **attrs) for column in (data + new_data)},
                **attrs
            )
            assert expect_table == Test.set()
            WAL.rollback(Test, log_path)
            assert init_table == Test.set()

        def test_rollback_satity_2(self, db_one_usage: Test_WAL.Db_one_use_yield):
            init_table = Test.set()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                Test.update("id < 1000", name="name + '123'")
                log_path = log_inst.log_file_path

            data, attrs = db_one_usage
            expect_table = Table(
                {(column[0],): RowList(
                    [column[0], column[1] + '123', *column[2:]], **attrs) for column in data},
                **attrs
            )
            assert expect_table == Test.set()
            WAL.rollback(Test, log_path)
            assert init_table == Test.set()

        def test_rollback_sanity_3(self, db_one_usage: Test_WAL.Db_one_use_yield):
            init_table = Test.set()

            with WAL(Test, Test_WAL.trans_name) as log_inst:
                Test.delete_table()
                log_path = log_inst.log_file_path

            assert len(Test.set()) == 0
            WAL.rollback(Test, log_path)
            assert Test.set() == init_table

        def test_rollback_with_holes(self, db_one_usage: Test_WAL.Db_one_use_yield):
            init_table = Test.set()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                Test.delete("id % 2 == 0")
                log_path = log_inst.log_file_path

            data, attrs = db_one_usage
            expect_table = Table(
                {(column[0],): RowList(column, **attrs) for column in data
                 if column[0] % 2 == 1},
                **attrs
            )
            assert expect_table == Test.set()
            WAL.rollback(Test, log_path)
            assert init_table == Test.set()

        def test_rollback_nothing(self, db_one_usage: Test_WAL.Db_one_use_yield):
            init_table = Test.set()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                log_path = log_inst.log_file_path
            assert Test.set() == init_table
            WAL.rollback(Test, log_path)
            assert init_table == Test.set()

        def test_rollback_everything(self, db_one_usage: Test_WAL.Db_one_use_yield):
            init_table = Test.set()
            with WAL(Test, Test_WAL.trans_name) as log_inst:
                Test.delete("id < 1000")
                log_path = log_inst.log_file_path

            _, attrs = db_one_usage
            assert Test.set() == Table({}, **attrs)
            WAL.rollback(Test, log_path)
            assert init_table == Test.set()
        
        def test_rollback_with_instance_all(self, clean_db: Callable[[], None]):
            clean_db()
            for i in range(5):
                Test(i, 'Janko', 'Hrasko').send()

            with WAL(Test, Test_WAL.trans_name) as log_inst:
                for i in range(5, 10):
                    Test(i, 'Janko', 'Hrasko').send()
                log_inst.log_file_struct.flush_logs(log_inst.log_f)
                log_inst.log_f.flush()
                os.fsync(log_inst.log_f)

                log_inst.commit()
                assert len(Test.set()) == 10

                report = WAL.check_consistency(Test, log_inst.log_file_path)
                assert len(report.not_applied_list) == 0

                log_inst.rollback()
                report = WAL.check_consistency(Test, log_inst.log_file_path)
                assert len(report.not_applied_list) == 5

            clean_db()
