from __future__ import annotations
import pytest #type:ignore[import-not-found]
import struct
import io
from collections.abc import Generator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Annotated

from database.tools.core.HighBaseModel import HighBaseModel
from database.tools.core.LowBaseModel import LowBaseModel
from database.tools.core.meta import BaseModelMeta
from database.tools.core.table_schema import TableSchema
from tests.test_database.test_model.test import Test

class Test_sanitize:

    @pytest.mark.parametrize(
            "val, expect",
            [
                (b'\x10\x20\x00', b'\x10\x20'),
                (b'\x10\x20\x30', b'\x10\x20\x30'),
                (b'', b''),
                (b'\x00\x00\x00', b'')
            ],
            ids=['default', 'nothing', 'empty', 'all']
    )
    def test_sanitize(self, val: bytes, expect: bytes):
        ans = LowBaseModel.sanitize(val)
        assert ans == expect

    def test_sanitize_wrong(self):
        ans = LowBaseModel.sanitize(b'\x14\x42')
        assert not (ans == b'\x14')


class Test_sanitize_str:

    @pytest.mark.parametrize(
            'val, expect',
            [
                ("'hello'", "hello"), ("hello", "hello"), ("hello'", "hello'"),
                ("'hello", "'hello"), ("", ""), ("''", ""),
                ("a", "a"), ("'", "'")
            ],
            ids=[
                'default', 'nothing', 'not_left',
                'not_right', 'empty', 'empty_str',
                'one_char_nothing', 'one_mark'
            ]
    )
    def test_sanitize_str(self, val: str, expect: str):
        ans = LowBaseModel.sanitize_str(val)
        assert ans == expect


@pytest.fixture
def model_factory_default_with_params() -> Callable[
                                            [int, str, str, str, str, str],
                                            object]:
    def _create(id: int, name: str, surname: str, birth_date: str,
                email: str, phone_num: str) -> object:

        @dataclass(slots=True)
        class Model(HighBaseModel, metaclass=BaseModelMeta):
            id: Annotated[int, 'unsigned int']
            name: Annotated[str, 20]
            surname: Annotated[str, 20]
            birth_date: Annotated[str, 10] | None
            email: Annotated[str, 40] | None = None
            phone_num: Annotated[str, 13] | None = None

            path: ClassVar[Path] = Path()

            _table_schema: ClassVar[TableSchema | None] = TableSchema(
                'Model',
                ['id', 'name', 'surname', 'birth_date', 'email', 'phone_num'],
                ('id',),
                '< I 20s 20s 10s 40s 13s',
                str(path)
            )

        return Model(id, name, surname, birth_date, email, phone_num)
    return _create

@pytest.fixture
def model_factory_2byte_mask() -> Callable[
                                    [int, str, str,
                                     str | None, str | None,
                                     str | None, str | None,
                                     str | None,],
                                    object]:
    def _create(id: int, name: str, surname: str,
                birth_date: str | None,
                email: str | None=None,
                phone_num: str | None=None,
                adress: str | None=None,
                city: str | None=None,
                postal_code: str | None=None) -> object:

        @dataclass(slots=True)
        class Model(HighBaseModel, metaclass=BaseModelMeta):
            id: Annotated[int, 'unsigned int']
            name: Annotated[str, 20]
            surname: Annotated[str, 20]
            birth_date: Annotated[str, 10] | None
            email: Annotated[str, 40] | None = None
            phone_num: Annotated[str, 13] | None = None
            address: Annotated[str, 40] | None = None
            city: Annotated[str, 20] | None = None
            postal_code: Annotated[str, 6] | None = None

            path: ClassVar[Path] = Path()
            byte_model: ClassVar[str] = 'I 20s 20s 10s 40s 13s 40s 20s 6s'
            _table_schema: ClassVar[TableSchema | None] = TableSchema(
                'Model',
                [
                    'id', 'name', 'surname', 'birth_date', 'email',
                    'phone_num', 'address', 'city', 'postal_code'
                ],
                ('id',),
                byte_model,
                str(path)
            )

        return Model(id, name, surname, birth_date, email,
                     phone_num, adress, city, postal_code)
    return _create

@pytest.fixture
def small_class_factory() -> Callable[[], type]:
    def _create() -> type:

        @dataclass(slots=True)
        class Model(HighBaseModel, metaclass=BaseModelMeta):
            id: Annotated[int, 'unsigned int'] | None
            name: Annotated[str, 20] | None
            surname: Annotated[str, 20]

            path: ClassVar[io.BytesIO] = io.BytesIO( #type: ignore
                bytes([0b00111110, 0b01111111, 0b11000000])
            )
            _table_schema: ClassVar[TableSchema | None] = TableSchema(
                'Model',
                ['id', 'name', 'surname'],
                ('id',),
                '< I 20s 20s',
                str(path)
            )

        return Model
    return _create

@pytest.fixture
def model_factory_2byte_mask_without_params() -> Callable[[], type]:
    def _create() -> type:

        @dataclass(slots=True)
        class Model(HighBaseModel, metaclass=BaseModelMeta):
            id: Annotated[int, 'unsigned int']
            name: Annotated[str, 20]
            surname: Annotated[str, 20]
            birth_date: Annotated[str, 10] | None
            email: Annotated[str, 40] | None = None
            phone_num: Annotated[str, 13] | None = None
            address: Annotated[str, 40] | None = None
            city: Annotated[str, 20] | None = None
            postal_code: Annotated[str, 6] | None = None

            path = Path()
            _table_schema: ClassVar[TableSchema | None] = TableSchema(
                'Model',
                [
                    'id', 'name', 'surname', 'birth_date', 'email',
                    'phone_num', 'address', 'city', 'postal_code'
                ],
                ('id',),
                '< I 20s 20s 10s 40s 13s 40s 20s 6s',
                str(path)
            )

        return Model
    return _create

class Test_getstate:

    def test_getstate_skip_prefix(self, model_factory_default_with_params: Callable):
        values = (
            5,
            'Kristián'.encode('utf-8'),
            'Veselý'.encode('utf-8'),
            '30.5.1992'.encode('utf-8'),
            'kris.v@gmail.com'.encode('utf-8'),
            '+421 916 854 255'.encode('utf-8')
        )

        model = model_factory_default_with_params(*values)
        expect = struct.pack('I 20s 20s 10s 40s 13s', *values)

        assert not (len(expect) == len(model.getstate()))
        assert len(expect) == len(model.getstate()) - 1

    def test_getstate_default(self, model_factory_default_with_params: Callable):
        values = (
            5,
            'Kristián'.encode('utf-8'),
            'Veselý'.encode('utf-8'),
            '30.5.1992'.encode('utf-8'),
            'kris.v@gmail.com'.encode('utf-8'),
            '+421 916 854 255'.encode('utf-8')
        )

        model = model_factory_default_with_params(*values)
        expect = b'\x00' + struct.pack('I 20s 20s 10s 40s 13s', *values)

        assert len(expect) == len(model.getstate())
        assert expect == model.getstate()

    def test_getstate_none_val(self, model_factory_default_with_params: Callable):
        values = (
            5,
            'Kristián'.encode('utf-8'),
            'Veselý'.encode('utf-8'),
            None, None, None
        )

        model = model_factory_default_with_params(*values)
        expect = b'\x1C' + struct.pack(
                            'I 20s 20s 10s 40s 13s',
                            values[0],
                            values[1],
                            values[2],
                            b'\x00' * 10,
                            b'\x00' * 40,
                            b'\x00' * 13
                        )

        assert len(expect) == len(model.getstate())
        assert expect == model.getstate()

    def test_getstate_2bytes_mask(self, model_factory_2byte_mask: Callable):
        values = (
            5,
            'Kristián'.encode('utf-8'),
            'Veselý'.encode('utf-8'),
            '30.5.1992'.encode('utf-8'),
            'kris.v@gmail.com'.encode('utf-8'),
            '+421 916 854 255'.encode('utf-8'),
            'Záhradnícka 5'.encode('utf-8'),
            None, None
        )

        model = model_factory_2byte_mask(*values)
        expect = b'\x01\x80' + struct.pack(
                                'I 20s 20s 10s 40s 13s 40s 20s 6s',
                                values[0], values[1], values[2],
                                values[3], values[4], values[5],
                                values[6],
                                b'\x00' * 20,
                                b'\x00' * 6
                                )

        assert len(expect) == len(model.getstate())
        assert expect == model.getstate()

    @pytest.fixture
    def model_factory_empty(self) -> object:

        class Model(HighBaseModel, metaclass=BaseModelMeta):
            byte_model = ''
            path = Path()

            def __init__(self):
                pass

            _table_schema: ClassVar[TableSchema | None] = TableSchema(
                'Model',
                [],
                (),
                byte_model,
                str(path)
            )

        return Model()

    def test_getstate_empty_class(self, model_factory_empty):
        model = model_factory_empty
        expect = b''

        assert len(expect) == len(model.getstate())
        assert expect == model.getstate()


class Test_setstate:

    def test_setstate_default(self, small_class_factory: Callable):
        data = (5, 'Jožko', 'Mrkvička')

        b_name = data[1].encode('utf-8')
        struct_code_name = b_name + b'\x00' * (20 - len(b_name))
        b_surname = data[2].encode('utf-8')
        struct_code_surname = b_surname + b'\x00' * (20 - len(b_surname))

        bstream = (
            b'\x00'
            + struct.pack('I', data[0])
            + struct_code_name
            + struct_code_surname
        )
        cls = small_class_factory()

        assert len(bstream) == cls.get_table_schema().inst_len

        inst = cls.setstate(bstream)

        assert inst.id == data[0]
        assert inst.name == data[1]
        assert inst.surname == data[2]

    def test_setstate_none_values(self, small_class_factory: Callable):
        data = (None, None, None)
        cls = small_class_factory()

        bstream = (
            bytes([0b11100000])
            + struct.pack('I', 0)
            + 2 * (b'\x00' * 20)
        )

        assert len(bstream) == cls.get_table_schema().inst_len

        inst = cls.setstate(bstream)

        assert inst.id == data[0]
        assert inst.name == data[1]
        assert inst.surname == data[2]

    def test_setstate_2bytes_prefix(self,
                                    model_factory_2byte_mask_without_params: Callable):
        data = (
            5,
            'Kristián',
            'Veselý',
            None, None, None,
            None, None, None
        )

        b_name = data[1].encode('utf-8')
        struct_code_name = b_name + b'\x00' * (20 - len(b_name))
        b_surname = data[2].encode('utf-8')
        struct_code_surname = b_surname + b'\x00' * (20 - len(b_surname))

        bstream = (
            b'\x1F' + b'\x80'
            + struct.pack('I', data[0])
            + struct_code_name
            + struct_code_surname
            + 129 * b'\x00'
        )

        cls = model_factory_2byte_mask_without_params()
        assert len(bstream) == cls.get_table_schema().inst_len

        inst = cls.setstate(bstream)

        for idx, attr in enumerate(cls.__slots__):
            assert data[idx] == getattr(inst, attr)

class Test_flip_prefix_bit:

    @pytest.mark.parametrize(
            "byte_mask, idx, expect_mask",
            [
                (bytes([0b11111111]), 5, bytes([0b11111011])),
                (bytes([0b11111111, 0b11111111, 0b11111110]), 23, bytes([0b11111111, 0b11111111, 0b11111111])),
                (bytes([0b11111111, 0b11111110, 0b11111111]), 15, bytes([0b11111111, 0b11111111, 0b11111111]))
            ],
            ids=['default', 'length 3 bytes', 'inside_edge']
    )
    def test_flip_prefix(self, byte_mask: bytes, idx: int, expect_mask: bytes):
        mask = bytearray(byte_mask)
        expec = LowBaseModel._flip_prefix_bit(mask, idx)
        assert expec == bytearray(expect_mask)


class Test_is_deleted_flag:

    fake_bytes = bytes([0b00111110, 0b01111111, 0b11000000])
    #data length - 45 B

    @pytest.mark.parametrize('pnt', [0, 45, 315, 360])
    def test_is_deleted_flag(self, pnt: int, small_class_factory: Callable):
        cls = small_class_factory()
        assert cls.is_deleted_flag(pnt, self.fake_bytes)

    def test_is_deleted_flag_reverse(self, small_class_factory: Callable):
        cls = small_class_factory()
        assert not cls.is_deleted_flag(720, self.fake_bytes)

    def test_is_deleted_flag_empty_end(self, small_class_factory: Callable):
        cls = small_class_factory()
        assert cls.is_deleted_flag(810, self.fake_bytes)

    def test_is_deleted_not_exist(self, small_class_factory: Callable):
        cls = small_class_factory()
        with pytest.raises(IndexError,
                            match='Pointer check_deleted_flag out of range'):
            cls.is_deleted_flag(1080, self.fake_bytes)

    def test_is_deleted_wrong_offser(self, small_class_factory: Callable):
        cls = small_class_factory()
        with pytest.raises(IndexError,
                            match='Pointer not on start of instance'):
            cls.is_deleted_flag(257, self.fake_bytes)


class Test_set_tombstone_flag:
    # working with real database model 'test_model'
    # instance length 108 B

    @pytest.fixture
    def setup_tomb(self) -> Generator[None, None, None]:
        with open(Test.path / 'data/tombstone.map', 'wb') as f:
            f.write(b'\x00\x00')
        yield
        open(Test.path / 'data/tombstone.map', 'wb').close()
    
    @pytest.mark.parametrize(
        'pnt, byte_1, byte_2',
        [(0, 128, 0), (864, 0, 128), (756, 1, 0), (1620, 0, 1)]
    )
    def test_set_tombstone_flag(self,
                                pnt: int, byte_1: int, byte_2: int,
                                setup_tomb: Generator[None, None, None]):
        Test._set_tombstone_flag(pnt)
        data = Test.read_tombstone()
        assert data[0] == byte_1 and data[1] == byte_2

    def test_set_tombstone_flag_none_pointer(self,
                                             setup_tomb: Generator[None, None, None]):
        Test._set_tombstone_flag(None)
        data = Test.read_tombstone()
        assert data[0] == 0 and data[1] == 0 and data[2] == 128


class Test_find_empty_space:
    # working with real database model 'test_model'
    # instance length 108 B

    @pytest.fixture
    def setup_tomb(self) -> Callable[[bytes], None]:
        def _create(bstream: bytes) -> None:
            with open(Test.path / 'data/tombstone.map', 'wb') as f:
                f.write(bstream)
        return _create

    @pytest.fixture
    def clean_tomb(self) -> Callable[[], None]:
        def _create() -> None:
            open(Test.path / 'data/tombstone.map', 'wb').close()
        return _create

    @pytest.mark.parametrize(
        "bytes, expect_pnt",
        [
            (bytes([0b00111111, 0b11111111]), 0),
            (bytes([0b10111101, 0b11101111]), 108),
            (bytes([0b11111110, 0b01011111]), 756),
            (bytes([0b11111111, 0b00110111]), 864),
            (bytes([0b11111111, 0b11111110]), 1620),
            (bytes([0b11111111, 0b11111111]), None),
            (bytes(([0b11111111] * 8) + [0b11011111]), 7128)
        ],
        ids=[
            'first_bit',
            'second_bit',
            'firste byte, last bit',
            'seconde byte, first bit',
            'second byte, last bit',
            'without empty space',
            'space in 9 bytes'
        ]
    )
    def test_find_empty_space_without_idx(self,
                                          bytes: bytes, expect_pnt: int,
                                          setup_tomb: Callable[[bytes], None],
                                          clean_tomb: Callable[[], None]):
        setup_tomb(bytes)
        assert Test.find_empty_space() == expect_pnt
        clean_tomb()

    @pytest.fixture
    def bytes_preset(self) -> bytes:
        return bytes([
            0b11111111, # 1
            0b11111101, # 2
            0b11011111, # 3
            0b11111111, # 4
            0b11111111, # 5
            0b11111111, # 6
            0b11111101, # 7
            0b11111111, # 8
            0b01111111, # 9
            0b11111101, # 10
            0b11111111, # 11
            0b11111111, # 12
            0b11110000  # 13
        ])

    @pytest.mark.parametrize(
            "pnt, expect_pnt",
            [(0, 1512), (756, 1512), (1080, 1512), (1404, 1512), (1512, 1944),
                (1620, 1944), (1728, 1944), (1836, 1944), (1944, 5832), (6804, 6912),
                (6912, 8424), (8532, 10800)]
    )
    def test_find_empty_space_with_idx(self,
                                       pnt: int, expect_pnt: int,
                                       bytes_preset: bytes,
                                       setup_tomb: Callable[[bytes], None],
                                       clean_tomb: Callable[[], None]):
        setup_tomb(bytes_preset)
        assert Test.find_empty_space(start_pnt=pnt) == expect_pnt
        clean_tomb()

    @pytest.fixture
    def bytes_preset_2(self) -> bytes:
        return bytes([
            0b11111111, #1
            0b11111111, #2
            0b11111111, #3
            0b11111111, #4
            0b11111111, #5
            0b11111111, #6
            0b11111111, #7
            0b11111111, #8
            0b11111111, #9
            0b11111111, #10
            0b11111111, #11
            0b11101111, #12
            0b11111111, #13
            0b11111111, #14
            0b11111111, #15
            0b11111110, #16
            0b11111011, #17
        ])

    @pytest.mark.parametrize(
            "pnt, expect_pnt",
            [(1836, 9828), (9828, 13716), (14040, 14364), (14364, None)],
            ids=[
                'middle',
                'tail 1',
                'tail 2',
                'find_none'
            ]
    )
    def test_find_empty_space_inside_sectors(self,
                                             pnt: int, expect_pnt: int,
                                             bytes_preset_2: bytes,
                                             setup_tomb: Callable[[bytes], None],
                                             clean_tomb: Callable[[], None]):
        setup_tomb(bytes_preset_2)
        assert Test.find_empty_space(start_pnt=pnt) == expect_pnt
        clean_tomb()
    
    def test_find_empty_space_all_positions(self,
                                            setup_tomb: Callable[[bytes], None],
                                            clean_tomb: Callable[[], None]):
        inst_len = Test.get_table_schema().inst_len
        test_byte_len = 30
        for pos in range(test_byte_len * 8):
            segment, offset = pos // 8, pos % 8
            data = bytes([
                ~(1 << (7 - offset)) & 0xff if i == segment else 255
                for i in range(test_byte_len)
            ])
            setup_tomb(data)
            for i in range(pos):
                assert Test.find_empty_space(start_pnt=i * inst_len) == pos * inst_len
            clean_tomb()
