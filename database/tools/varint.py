import mmap
from collections.abc import Iterable

class VarInt:
    """
    class providing functions to manipulate with VarInts.
    VarInts are only sequence of bytes that can be interpreted as VarInt
    """

    @staticmethod
    def _gen_chunks(n: int) -> Iterable[int]:
        while n:
            yield n & 0b01111111
            n >>= 7

    @staticmethod
    def to_varint(num: int) -> bytes:
        if num == 0:
            return (0).to_bytes(1, 'little', signed=False)
        chunks = list(VarInt._gen_chunks(num))
        return b''.join([
            ((num | 0b10000000) if idx < len(chunks) - 1 else num).to_bytes(1, byteorder='big', signed=False)
            for idx, num in enumerate(chunks)
        ])

    @staticmethod
    def to_int(byte_buff: bytes | memoryview | mmap.mmap) -> list[int]:
        ans_stack = []
        acc, iiter = 0, 0

        for byte in byte_buff:
            acc += (byte & 0b01111111) * (1 << (iiter * 7))
            iiter += 1
            if byte & 0b10000000 != 0b10000000:
                ans_stack.append(acc)
                acc, iiter = 0, 0
        return ans_stack

    @staticmethod
    def find_fst_varint(bytes: bytes | memoryview | mmap.mmap) -> bytes:
        bytearr = bytearray()
        for byte in bytes:
            bytearr.append(byte)
            if byte < 128:
                break
        return bytearr
