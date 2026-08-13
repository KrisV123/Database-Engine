from __future__ import annotations

import struct
from platform import system
from dataclasses import dataclass, field
from json import load, dump, loads, dumps
from pathlib import Path
from math import ceil
from typing import Any
from textwrap import dedent

OS = system()

def get_byte_model_list(byte_model: str) -> list[str]:
    """return list of every C type from byte_model in list"""

    byte_model = byte_model.lstrip(' ')

    if len(byte_model) > 0 and byte_model[0] in ('@', '=', '<', '>', '!'):
        byte_model = byte_model[1:]

    type_list, num_list = [], []
    for char in byte_model:
        if char == ' ':
            continue
        if char.isdigit():
            num_list.append(char)
        elif isinstance(char, str):
            if char in ('s', 'p') and len(num_list) == 0:
                raise AttributeError(
                    'invalid byte model. Types s and p need to have byte ammount'
                )
            typ = ''.join(num_list) + char
            type_list.append(typ)
            num_list = []
    return type_list

def get_mask_len(byte_model_list: list[str]) -> int:
    """returns mask size in bytes"""

    bit_len = len(byte_model_list)
    return ceil(bit_len / 8)

def get_endianness_symbol(byte_model: str) -> str:
    """
    returns endianness symbol from byte_model string.
    If there isn't any, empty string will be returend
    """

    byte_model = byte_model.lstrip(' ')
    if len(byte_model) > 0:
        fst_char = byte_model[0]
        return fst_char if fst_char in ('@', '=', '<', '>', '!') else ''
    else:
        return ''

def get_attr_offset_dict(byte_model_list: list[str],
                         attributes: list[str]) -> dict[str, int]:
    attr_offset_dict = {}
    offset = 0
    for attr, ctype in zip(attributes, byte_model_list):
        attr_offset_dict[attr] = offset
        offset += struct.calcsize(ctype)
    return attr_offset_dict

def get_attr_struct_dict(endianness_symbol: str, attr_ctype_dict: dict[str, str]):
    return {
        attr: struct.Struct(endianness_symbol + ctype)
        for attr, ctype in attr_ctype_dict.items()
    }

class TableSchemaError(Exception):
    pass


@dataclass(slots=True)
class TableSchema:
    """
    Object, that that holds in-memory data about Model.
    Also cache some derived metadata.
    """

    model_name: str
    attributes: list[str]
    primary_key: tuple[str, ...]
    byte_model: str
    model_path: str

    byte_model_list: list[str] = field(init=False)
    mask_len: int = field(init=False)
    inst_len: int = field(init=False)
    endianness_symbol: str = field(init=False)

    attr_ord_dict: dict[str, int] = field(init=False)
    attr_offset_dict: dict[str, int] = field(init=False)
    attr_ctype_dict: dict[str, str] = field(init=False)
    attr_struct_dict: dict[str, struct.Struct] = field(init=False)

    packer: struct.Struct = field(init=False)

    def __post_init__(self):
        self.byte_model_list = get_byte_model_list(self.byte_model)
        self.mask_len = get_mask_len(self.byte_model_list)
        self.inst_len = self.mask_len + struct.calcsize(self.byte_model)
        self.endianness_symbol = get_endianness_symbol(self.byte_model)

        self.attr_ord_dict = {attr: ord for ord, attr in enumerate(self.attributes)}
        self.attr_offset_dict = get_attr_offset_dict(self.byte_model_list, self.attributes)
        self.attr_ctype_dict = {attr: ctype for attr, ctype in zip(self.attributes, self.byte_model_list)}
        self.attr_struct_dict = get_attr_struct_dict(self.endianness_symbol, self.attr_ctype_dict)

        self.packer = struct.Struct(self.byte_model)


    def __setattr__(self, name: Any, value: Any) -> None:
        if hasattr(self, name):
            raise TableSchemaError('TableSchema is frozen')
        object.__setattr__(self, name, value)

    @classmethod
    def normalize_path(cls, path: str | Path):
        new_path = str(path) if isinstance(path, Path) else path

        if OS == 'Windows':
            new_path = new_path.lower()

        return new_path

    @classmethod
    def init_meta(cls, model: type) -> TableSchema:
        """creates new meta.json in model's data"""

        meta = {
            'model_name': model.__name__,
            'attributes': [name for name in model.__slots__],
            'primary_key': model.primary_key,
            'byte_model': model.byte_model,
            'model_path': cls.normalize_path(model.path)
        }
        with open(model.path / 'data/meta.json', 'w') as f:
            dump(meta, f, indent=4)

        return TableSchema(**meta)

    @classmethod
    def create_table_schema_from_file(cls, meta_path: str | Path) -> TableSchema:
        """creates model's TableSchema, witch is memory cache of meta.json"""

        with open(meta_path, 'r') as f:
            meta: dict = load(f)

        meta['model_path'] = cls.normalize_path(meta['model_path'])

        return TableSchema(**meta)

    @classmethod
    def check_table_schema(cls,
                           model: type,
                           meta_path: str | Path) -> TableSchema:
        """check, if current model's metadata match with model's meta.json"""

        table_schema = cls.create_table_schema_from_file(meta_path)

        if model.__name__ != table_schema.model_name:
            raise TableSchemaError(dedent(
                f"""
                Model name don't match with model name in TableSchema
                meta name:  {table_schema.model_name}
                setup name: {model.__name__}
                """
            ))

        attributes = [name for name in model.__slots__]
        if attributes != table_schema.attributes:
            raise TableSchemaError(dedent(
                f"""
                Model's attributes don't match with model's attributes in TableSchema
                meta attributes:  {repr(table_schema.attributes)}
                setup attributes: {repr(attributes)}
                """
            ))

        if model.primary_key != tuple(table_schema.primary_key):
            raise TableSchemaError(dedent(
                f"""
                Model's primary key don't match with model's primary key in TableSchema
                meta primary key:  {repr(table_schema.primary_key)}
                setup primary key: {repr(model.primary_key)}
                """
            ))

        if model.byte_model != table_schema.byte_model:
            raise TableSchemaError(dedent(
                f"""
                Model's byte_model don't match with model's byte model in TableSchema
                meta byte_model:  {table_schema.byte_model}
                setup byte_model: {model.byte_model}
                """
            ))

        if cls.normalize_path(model.path) != table_schema.model_path:
            raise TableSchemaError(dedent(
                f"""
                Model's path don't match with model's path in TableSchema
                meta path:  {table_schema.model_path}
                setup path: {model.path}
                """
            ))

        return table_schema

    def to_json(self) -> str:
        data = {
            'model_name': self.model_name,
            'attributes': self.attributes,
            'primary_key': self.primary_key,
            'byte_model': self.byte_model,
            'model_path': self.normalize_path(self.model_path)
        }
        return dumps(data)
