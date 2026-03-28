import pytest #type:ignore[import-not-found]
from database.tools.varint import VarInt

class Test_VarInt:
    test_tuples: list[tuple[int, bytes]] = [
        (0, b'\x00'),
        (1, b'\x01'),
        (67, b'\x43'),
        (127, b'\x7f'),
        (128, b'\x80\x01'),
        (129, b'\x81\x01'),
        (255, b'\xff\x01'),
        (256, b'\x80\x02'),
        (300, b'\xac\x02'),
        (4856, b'\xf8\x25'),
        (258, b'\x82\x02'),
        (258888, b'\xc8\xe6\x0f'),
        (12345, b'\xb9\x60'),
        (16384, b'\x80\x80\x01'),
        (987654321, b'\xb1\xd1\xf9\xd6\x03'),
        (4294967295, b'\xff\xff\xff\xff\x0f'),
    ]

    @pytest.mark.parametrize(
            "num, varint",
            test_tuples,
    )
    def test_to_varint(self, num: int, varint: bytes):
        assert VarInt.to_varint(num) == varint 

    @pytest.mark.parametrize(
            "num, varint",
            test_tuples
    )
    def test_to_int(self, num: int, varint: bytes):
        assert VarInt.to_int(varint) == [num]
    
    @pytest.mark.parametrize(
            "byte_seq, varint_list",
            [
                (b'\x00\x00\x00\x00\x00\x00', [0, 0, 0, 0, 0, 0]),
                (b'\x01\x02', [1, 2]),
                (b'\x01\x02\x03\x04', [1, 2, 3, 4]),
                (b'\xac\x02\x05', [300, 5]),
                (b'\x96\x01\xac\x02', [150, 300]),
                (b'\x96\x01\xac\x02\x07', [150, 300, 7]),
                (b'\xff\xff\xff\x7f\x01', [0x0FFFFFFF, 1]),
                (b'\xff\xff\xff\xff\x0f\x01', [4294967295, 1]),
                (b'\xff\xff\xff\xff\x0f\xff\xff\xff\xff\x0f', [4294967295, 4294967295]),
                (b'\x96\x01\xff\xff\xff\x7f\xac\x02', [150, 0x0FFFFFFF, 300]),
                (b'\x00\xac\x02\x01', [0, 300, 1]),
                (b'\xac\x02\xff\xff\xff\x7f\x00', [300, 0x0FFFFFFF, 0]),
            ],
            ids = [
                "zeros_multiple",
                "small_two_values",
                "small_four_values",
                "mix_small_large_300_5",
                "mixed_two_varints_150_300",
                "mixed_three_varints_150_300_7",
                "big_followed_by_small",
                "max32_followed_by_small",
                "two_max32_values",
                "mixed_lengths_150_big_300",
                "starts_with_zero",
                "ends_with_zero",
            ]
    )
    def test_to_varint_sequence(self, byte_seq: bytes, varint_list: list[int]):
        assert VarInt.to_int(byte_seq) == varint_list

    @pytest.mark.parametrize(
            "varint_buff, fst_varint",
            [
                (b'\x76\x76\x76\x77\x77', b'v'),
                (b'\x00', b'\x00'),
                (b'\x01\x02\x03', b'\x01'),
                (b'\x7f\x80', b'\x7f'),
                (b'\x80\x01', b'\x80\x01'),
                (b'\xff\x01\x7f', b'\xff\x01'),
                (b'\xac\x02rest', b'\xac\x02'),
                (b'\xe5\x8e&tail', b'\xe5\x8e&'),
                (b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01',
                    b'\xff\xff\xff\xff\xff\xff\xff\xff\xff\x01'),
                (b'\x81\x80\x80\x80\x00after', b'\x81\x80\x80\x80\x00'),
                (b'\x8f\xff\xff\xff\x0fmore', b'\x8f\xff\xff\xff\x0f'),
            ],
            ids = [
                "single-byte_sequence",
                "zero_value",
                "small_values",
                "max_single_byte",
                "two_byte_128",
                "two_byte_255",
                "two_byte_300",
                "three_byte_624485",
                "max_uint64_varint",
                "multi_byte_mixed_1",
                "multi_byte_mixed_2",
            ]
    )
    def test_find_fst_varint(self, varint_buff: bytes, fst_varint: bytes):
        assert VarInt.find_fst_varint(varint_buff) == fst_varint