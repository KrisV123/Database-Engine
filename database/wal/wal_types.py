from dataclasses import dataclass
from typing import Literal
from enum import Enum

class Operator(Enum):
    SEND = b'\x01'
    UPDATE = b'\x02'
    DELETE = b'\x03'
    DELETE_TABLE = b'\x04'


class EntryPoints:

    @dataclass(slots=True, frozen=True)
    class Entry:
        operator: Operator
        start_pnt: int
        old_data: bytes | None
        new_data: bytes | None
        meta: bytes | None


    @dataclass(frozen=True)
    class SendEntry:
        new_data: bytes


    @dataclass(frozen=True)
    class UpdateEntry:
        start_pnt: int
        old_data: bytes
        new_data: bytes


    @dataclass(frozen=True)
    class DeleteEntry:
        start_pnt: int
        old_data: bytes


    @dataclass(frozen=True)
    class DeleteTableEntry:
        old_data: bytes
        meta: bytes


    UserEntry = SendEntry | UpdateEntry | DeleteEntry | DeleteTableEntry
