from typing import Any, Union, ClassVar, get_args, get_origin, get_type_hints, assert_never
from types import UnionType, NoneType
from pathlib import Path

from database.tools.core.types import T_AcceptType, C_TYPES_TO_STRUCT

class InvalidTableError(BaseException):
    pass


class Typing_helper:
    """class with helper methods for typing and generating byte_model"""

    @classmethod
    def get_ctype_from_orig_type(cls, orig_type: T_AcceptType, meta: str):

        struct_dict = C_TYPES_TO_STRUCT[orig_type]
        struct_char = struct_dict.get(meta)
        if struct_char is not None:
            return struct_char
        else:
            raise InvalidTableError(f'{meta} is not valid c_type')

    @classmethod
    def handle_annotated_type(cls, orig_type: T_AcceptType, meta: int | str) -> str:
        if orig_type is NoneType:
            raise InvalidTableError('NoneType can not be annotated')
        elif orig_type is bool:
            raise InvalidTableError('there is no point in annotating bool')

        elif orig_type is str:
            if isinstance(meta, str):
                if len(meta) < 1:
                    raise InvalidTableError(
                        "string should not be empty"
                    )
                if meta[-1] == "p" and meta[:-1].isdigit():
                    return meta
                return cls.get_ctype_from_orig_type(orig_type, meta)
            elif isinstance(meta, int):
                str_len = str(meta)
                return str_len + 's'
            else:
                raise InvalidTableError(
                    'str should contain string size in int, c_type or pascal string with size'
                )

        elif orig_type in (int, float):
            if isinstance(meta, int):
                raise InvalidTableError(
                    f'{repr(orig_type)} should contain c_type information in str'
                )
            return cls.get_ctype_from_orig_type(orig_type, meta)

        else:
            raise InvalidTableError(f'table cannot contain {repr(orig_type)} type')

    @classmethod
    def handle_type(cls, typ: type) -> str:
        if typ in (None, NoneType):
            raise InvalidTableError(
                'NoneType can only be second type'
            )
        if typ is str:
            raise InvalidTableError(
                'str type is prohibited. Use Annotated from typing module with str'
            )
        elif typ is int:
            return 'l'
        elif typ is bool:
            return '?'
        elif typ is float:
            return 'd'
        elif get_origin(typ) in (Union, UnionType):

            args = get_args(typ)
            if len(args) != 2:
                raise InvalidTableError('union type can only be with two types')
            if args[1] is not type(None):
                raise InvalidTableError('second type can only be None')

            return cls.handle_type(args[0])

        elif hasattr(typ, '__metadata__'):
            # that means, it's Annotated type, there is no other way to check it

            nested_typ: T_AcceptType = typ.__origin__
            meta = typ.__metadata__[0]
            return cls.handle_annotated_type(nested_typ, meta)

        raise InvalidTableError(f'type {repr(typ)} can not appear')

    @classmethod
    def create_byte_model(cls, annotations: dict[str, type]) -> str:
        byte_model = []
        for typ in annotations.values():
            if get_origin(typ) is ClassVar:
                continue
            byte_model.append(cls.handle_type(typ))
        return '< ' + ' '.join(byte_model)


class BaseModelMeta(type):

    def __new__(cls, name: str, bases: tuple[type], namespace: dict[str, Any]):
        byte_model = namespace.get('byte_model')

        if '__annotations__' in namespace and byte_model is None:
            new_cls = super().__new__(cls, name, bases, namespace)
            annotations = get_type_hints(new_cls, include_extras=True)
            setattr(new_cls, 'byte_model', Typing_helper.create_byte_model(annotations))
            return new_cls

        return super().__new__(cls, name, bases, namespace)
