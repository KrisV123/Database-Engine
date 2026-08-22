from types import NoneType
from typing import TypedDict

AcceptTypes = int | float | bool | str | None

class C_type_meta(TypedDict):
    c_type: str
    py_type: type
    size: int | None


STRUCT_FORMAT_INFO: dict[str, C_type_meta] = {
    'x': {'c_type': 'pad byte',           'py_type': NoneType, 'size': 1},
    'c': {'c_type': 'char',               'py_type': bytes,    'size': 1},
    'b': {'c_type': 'signed char',        'py_type': int,      'size': 1},
    'B': {'c_type': 'unsigned char',      'py_type': int,      'size': 1},
    '?': {'c_type': '_Bool',              'py_type': bool,     'size': 1},
    'h': {'c_type': 'short',              'py_type': int,      'size': 2},
    'H': {'c_type': 'unsigned short',     'py_type': int,      'size': 2},
    'i': {'c_type': 'int',                'py_type': int,      'size': 4},
    'I': {'c_type': 'unsigned int',       'py_type': int,      'size': 4},
    'l': {'c_type': 'long',               'py_type': int,      'size': 4},
    'L': {'c_type': 'unsigned long',      'py_type': int,      'size': 4},
    'q': {'c_type': 'long long',          'py_type': int,      'size': 8},
    'Q': {'c_type': 'unsigned long long', 'py_type': int,      'size': 8},
    'f': {'c_type': 'float',              'py_type': float,    'size': 4},
    'd': {'c_type': 'double',             'py_type': float,    'size': 8},
    's': {'c_type': 'char[]',             'py_type': bytes,    'size': None},
    'p': {'c_type': 'pascal string',      'py_type': bytes,    'size': None}
}

T_placeholder_keys = type[None] | type[bool] | type[int] | type[float] | type[bytes]
T_placeholder_values = NoneType | bool | int | float | bytes

PLACEHOLDER: dict[T_placeholder_keys, T_placeholder_values] = {
    NoneType: None,
    bool: False,
    int: 0,
    float: 1.0,
    bytes: b'\x00',
}

INT_C_TYPES_TO_STRUCT: dict[str, str] = {
    'signed char': 'b',
    'unsigned char': 'B',
    'short': 'h',
    'unsigned short': 'H',
    'int': 'i',
    'unsigned int': 'I',
    'long': 'l',
    'unsigned long': 'L',
    'long long': 'q',
    'unsigned long long': 'Q',
}

FLOAT_C_TYPES_TO_STRUCT: dict[str, str] = {
    'float': 'f',
    'double': 'd',
}

NONE_C_TYPES_TO_STRUCT: dict[str, str] = {
    'pad byte': 'x'
}

BOOL_C_TYPES_TO_STRUCT: dict[str, str] = {
    '_Bool': '?'
}

STR_C_TYPES_TO_STRUCT: dict[str, str] = {
    'char': 'c',
    'char[]': 's',
    'pascal string': 'p',
}

T_AcceptType = type[NoneType] | type[bool] | type[int] | type[float] | type[str]

C_TYPES_TO_STRUCT: dict[T_AcceptType, dict[str, str]] = {
    NoneType: NONE_C_TYPES_TO_STRUCT,
    bool: BOOL_C_TYPES_TO_STRUCT,
    int: INT_C_TYPES_TO_STRUCT,
    float: FLOAT_C_TYPES_TO_STRUCT,
    str: STR_C_TYPES_TO_STRUCT
}
