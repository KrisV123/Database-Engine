from __future__ import annotations
import pytest #type:ignore[import-not-found]
from collections.abc import Generator

from database.core.table import Table
from database.core.row import RowList
from tests.test_database.test_model.test import Test

class Test_send:

    def test_send_default_1(self):
        Test.delete_table()
        data = (
            1, 'Kristian', 'Vesely', '10.08.1925',
            None, '0957_254_486'
        )

        inst = Test(*data)
        inst.send()
        with open(Test.path / 'data/data.bin', 'rb') as f:
            db_bytes = f.read()

        db_inst = Test.setstate(db_bytes)
        db_inst_data = tuple([getattr(db_inst, attr) for attr in Test.__slots__]) #type:ignore[attr-defined]

        assert db_inst_data == data
        Test.delete_table()

    def test_send_default_2(self):
        Test.delete_table()
        data = [
            'Kristian', 'Vesely', None,
            'jozko_1@gmail.com', '0957_254_486'
        ]

        for i in range(5):
            inst = Test(i ,*data)
            inst.send()

        with open(Test.path / 'data/data.bin', 'rb') as f:
            db_bytes = f.read()

        inst_len = Test.get_table_schema().inst_len
        instances = [
            Test.setstate(db_bytes[i:i + inst_len])
            for i in range(0, len(db_bytes), inst_len)
        ]
        insts_attribs = [
            [getattr(db_inst, attr) for attr in Test.__slots__] # type: ignore[attr-defined]
            for db_inst in instances
        ]

        for data, predic in zip([[i] + data for i in range(5)], insts_attribs):
            assert data == predic
        Test.delete_table()

    def test_send_find_empty_space(self):
        Test.delete_table()
        placeholder_data = (
            1, 'Kristian', 'Vesely', None, 'jozko_1@gmail.com', '0957_254_486'
        )
        replace_data = (5, 'Kristian', 'Vesely', '10.08.1925', None, None)

        for i in range(5):
            inst = Test(*placeholder_data)
            inst.send()

        with open(Test.path / 'data/tombstone.map', 'wb') as f:
            f.write(bytes([0b11101111]))

        inst = Test(*replace_data)
        inst.send()

        with open(Test.path / 'data/data.bin', 'r+b') as f:
            db_bytes = f.read()

        inst_len = Test.get_table_schema().inst_len
        instances = [
            Test.setstate(db_bytes[i:i + inst_len])
            for i in range(0, len(db_bytes), inst_len)
        ]
        insts_attribs = [
            tuple(getattr(db_inst, attr) for attr in Test.__slots__) # type: ignore[attr-defined]
            for db_inst in instances
        ]

        for i in range(5):
            if i == 3:
                assert replace_data == insts_attribs[i]
            else:
                assert placeholder_data == insts_attribs[i]
        Test.delete_table()

@pytest.fixture
def db_attribs() -> dict[str, int]:
    return {
        'id': 0, 'name': 1, 'surname': 2,
        'birth_date': 3, 'email': 4, 'phone_num': 5
    }

class Test_set:

    @pytest.fixture
    def setup_db(self) -> Generator[None, None, None]:
        Test.delete_table()
        for i in range(5):
            model = Test(
                i, 'Kristian', 'Vesely', '20.01.2001',
                'kris.v@gmail.com', None
            )
            model.send()
        yield
        Test.delete_table()

    def test_set_default(self,
                         setup_db: Generator[None, None, None],
                         db_attribs: dict[str, int]):
        column = RowList([
            'Kristian', 'Vesely', '20.01.2001', 'kris.v@gmail.com', None], **db_attribs
        )
        expect = Table({
            (i,): RowList(
                [i, *column],
                **db_attribs)
            for i in range(5)},
            **db_attribs
        )

        db_table = Test.set()

        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes

    def test_set_wrong_str(self,
                           setup_db: Generator[None, None, None],
                           db_attribs: dict[str, int]):
        column = [
            "'Kristian'", "'Vesely'", "'20.01.2001'",
            "'kris.v@gmail.com'", None
        ]
        expect = Table({
            (i,): RowList([i, *column], **db_attribs)
            for i in range(5)},
            **db_attribs
        )

        db_table = Test.set()
        assert not (dict(db_table) == dict(expect))
        assert not (db_table.attributes == {'ahoj': 0, 'ferko': 1})

    def test_set_empty_table_without_params(self):
        db_table = Test.set()
        expect_attrs = {attr: idx for idx, attr in enumerate(Test.__slots__)}
        expect = Table(dict(), **expect_attrs)

        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes

    def test_set_empty_table_with_params(self):
        search_attrs = ('Name', 'Surname')
        db_table = Test.set(*search_attrs)
        expect_attrs = {attr: idx for idx, attr in enumerate(search_attrs)}
        expect = Table(dict(), **expect_attrs)

        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes

    def test_set_with_params(self, setup_db: Generator[None, None, None]):
        column = ['Kristian', None]
        expect_attrs = {'name': 0, 'phone_num': 1}
        expect = Table({
            (i,): RowList(column, **expect_attrs)
            for i in range(5)},
            **expect_attrs
        )

        db_table = Test.set('name', 'phone_num')
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes

    def test_set_different_attr_ord(self):
        Test.delete_table()
        for i in range(5):
            model = Test(
                i, 'Kristian', 'Vesely', None,
                'kris.v@gmail.com', None
            )
            model.send()

        column = ['Kristian', None, None]
        expect_attrs = {'name': 0, 'phone_num': 1, 'birth_date': 2}
        expect = Table({
            (i,): RowList(column, **expect_attrs)
            for i in range(5)},
            **expect_attrs
        )

        db_table = Test.set('name', 'phone_num', 'birth_date')
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        Test.delete_table()


class Test_delete:
    # working with real database model 'test_model'
    # instance length 108 B

    @pytest.fixture
    def setup_db(self) -> Generator[None, None, None]:
        Test.delete_table()
        for i in range(16):
            model = Test(
                i, 'Kristian', 'Vesely', '20.01.2001',
                'kris.v@gmail.com', None
            )
            model.send()
        yield
        Test.delete_table()

    def test_delete_default_1(self, setup_db: Generator[None, None, None]):
        Test.delete("id % 2 == 0")
        column = Test.read_tombstone()
        for i in column:
            bit_list = [
                1 if i & (1 << j) != 0 else 0
                for j in range(7, -1, -1)
            ]
            guess = [0 if not (j % 2) else 1 for j in range(8)]
            for k in range(8):
                assert bit_list[k] == guess[k]

    def test_delete_default_2(self, setup_db: Generator[None, None, None]):
        deleted_count = Test.delete("id % 2 == 0")

        expect_attrs = {
            'id': 0, 'name': 1, 'surname': 2,
            'birth_date': 3, 'email': 4, 'phone_num': 5
        }
        column = [
            'Kristian', 'Vesely', '20.01.2001',
            'kris.v@gmail.com', None
        ]
        expect = Table({
            (i,) : RowList([i, *column], **expect_attrs)
            for i in range(16)
            if i % 2 == 1
        }, **expect_attrs)

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        assert deleted_count == 8

    def test_delete_default_2_wrong_str(self, setup_db: Generator[None, None, None]):
        deleted_count = Test.delete("id % 2 == 0")
        expect_attrs = {
            'id': 0, 'name': 1, 'surname': 2,
            'birth_date': 3, 'email': 4, 'phone_num': 5
        }
        column = [
            "'Kristian'", "'Vesely'", "'20.01.2001'",
            "'kris.v@gmail.com'", None
        ]
        expect = Table({
            (i,) : RowList([i, *column], **expect_attrs)
            for i in range(16)
            if i % 2 == 1
        }, **expect_attrs)

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert not (dict(db_table) == dict(expect))
        assert db_table.attributes == expect.attributes
        assert deleted_count == 8

    def test_delete_default_3(self, setup_db: Generator[None, None, None]):
        deleted_count = Test.delete("id % 2 == 0")

        expect_attrs = {
            'id': 0, 'name': 1, 'surname': 2,
            'birth_date': 3, 'email': 4, 'phone_num': 5
        }
        column = [
            'Kristian', 'Vesely', '20.01.2001',
            'kris.v@gmail.com', None
        ]
        expect = Table({
            (i,) : RowList([i, *column], **expect_attrs)
            for i in range(16)
            if i % 2 == 1
        }, **expect_attrs)

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        assert deleted_count == 8

    def test_delete_del_all(self, setup_db: Generator[None, None, None]):
        deleted_count = Test.delete("True")

        expect_attrs = {
            'id': 0, 'name': 1, 'surname': 2,
            'birth_date': 3, 'email': 4, 'phone_num': 5
        }
        expect = Table(dict(), **expect_attrs)

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        assert deleted_count == 16

    def test_delete_del_none(self):
        Test.delete_table()
        for i in range(100):
            model = Test(
                i, 'Kristian', 'Vesely', '20.01.2001',
                'kris.v@gmail.com', None
            )
            model.send()
        deleted_count = Test.delete("name != 'Kristian'")

        expect_attrs = {
            'id': 0, 'name': 1, 'surname': 2,
            'birth_date': 3, 'email': 4, 'phone_num': 5
        }
        column = [
            'Kristian', 'Vesely', '20.01.2001',
            'kris.v@gmail.com', None
        ]
        expect = Table({
            (i,): RowList([i, *column], **expect_attrs)
            for i in range(100)},
            **expect_attrs
        )

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        assert deleted_count == 0
        Test.delete_table()

    def test_telete_empty_table(self):
        Test.delete_table()
        deleted_count = Test.delete("name == awdawd")

        expect_attrs = {
            'id': 0, 'name': 1, 'surname': 2,
            'birth_date': 3, 'email': 4, 'phone_num': 5
        }
        expect = Table(dict(), **expect_attrs)

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        assert deleted_count == 0
        Test.delete_table()


class Test_update:

    TupleGroup = tuple[int, str, str, str | None, str | None, str | None]
    QuadTestTuple = tuple[TupleGroup, TupleGroup, TupleGroup, TupleGroup]

    @pytest.fixture
    def table_meta(self) -> QuadTestTuple:
        model_1 = (
            1, 'Kristian', 'Vesely', '20.01.2001',
            'kris.v@gmail.com', None
        )
        model_2 = (
            2, 'Jozko', 'Mrkvicka', '25.05.2514',
            'jozko.m@gmail.com', '0908_524_545'
        )
        model_3 = (
            3, 'Andrej', 'Mesko', None,
            'andrewmes007@gmail.com', '2564_568_524'
        )
        model_4 = (
            4, 'Andrej', 'Mesko', None,
            None, '1234_567_890'
        )

        return model_1, model_2, model_3, model_4

    def test_update_default(self, db_attribs: dict[str, int]):
        Test.delete_table()
        for i in range(16):
            model = Test(
                i, 'Kristian', 'Vesely', '20.01.2001',
                'kris.v@gmail.com', None
            )
            model.send()
        
        updated_count = Test.update("id >= 10", name = "'Jožko'")

        column_1 = [
            'Kristian', 'Vesely', '20.01.2001',
            'kris.v@gmail.com', None
        ]
        column_2 = [
            'Jožko', 'Vesely', '20.01.2001',
            'kris.v@gmail.com', None
        ]

        expect_1 = {(i,): RowList([i, *column_1], **db_attribs)
                    for i in range(10)}
        expect_2 = {(i,): RowList([i, *column_2], **db_attribs)
                    for i in range(10, 16)}
        expect = dict()
        expect.update(expect_1)
        expect.update(expect_2)
        expect = Table(expect, **db_attribs)

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        assert updated_count == 6
        Test.delete_table()

    def test_update_specific(self,
                             table_meta: QuadTestTuple,
                             db_attribs: dict[str, int]):
        Test.delete_table()
        model_1, model_2, model_3, model_4 = table_meta

        meta_model = table_meta
        for model_tuple in meta_model:
            model = Test(*model_tuple)
            model.send()

        updated_count = Test.update("name == 'Andrej'", name = "name + 'Moah'")

        expect = Table({
            (model_1[0],): RowList(model_1, **db_attribs),
            (model_2[0],): RowList(model_2, **db_attribs),
            (model_3[0],): RowList([
                model_3[0], model_3[1] + 'Moah',
                model_3[2], *model_3[3:]], **db_attribs),
            (model_4[0],): RowList([
                model_4[0], model_4[1] + 'Moah',
                model_4[2], *model_4[3:]], **db_attribs)},
            **db_attribs
        )

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        assert updated_count == 2
        Test.delete_table()

    def test_update_from_none_to_val(self,
                                     table_meta: QuadTestTuple,
                                     db_attribs: dict[str, int]):
        Test.delete_table()
        model_1, model_2, model_3, model_4 = table_meta

        for model_tuple in table_meta:
            model = Test(*model_tuple)
            model.send()

        Test.update(
            "(phone_num == None) and (name == 'Kristian')",
            phone_num = "'1111_111_111'"
        )

        expect = Table({
            (model_1[0],): RowList([*model_1[:-1], '1111_111_111'], **db_attribs),
            (model_2[0],): RowList(model_2, **db_attribs),
            (model_3[0],): RowList(model_3, **db_attribs),
            (model_4[0],): RowList(model_4, **db_attribs)},
            **db_attribs
        )

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        Test.delete_table()

    def test_update_empty_table(self, db_attribs):
        Test.delete_table()
        updated_count = Test.update("True", name='Honza')

        expect = Table(dict(), **db_attribs)

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        assert updated_count == 0
        Test.delete_table()

    def test_update_all(self, db_attribs):
        Test.delete_table()
        data = [
            1, 'Kristian', 'Vesely', '20.01.2001',
            'kris.v@gmail.com', None
        ]
        for _ in range(16):
            model = Test(*data)
            model.send()

        updated_count = Test.update("True", name="'Honza'")

        expect = Table({
            (data[0],): RowList([data[0]] + ['Honza'] + data[2:], **db_attribs)
            for i in range(16)},
            **db_attribs
        )

        db_table = Test.set()
        assert len(db_table) == len(expect)
        assert dict(db_table) == dict(expect)
        assert db_table.attributes == expect.attributes
        assert updated_count == 16
        Test.delete_table()
