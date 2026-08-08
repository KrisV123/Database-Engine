import pytest

from types import NoneType

from database.tools.core.HighBaseModel import HighBaseModel
from database.tools.core.meta import Typing_helper, InvalidTableError
from database.tools.core.types import T_AcceptType

class Test_Typing_helper:

    @pytest.mark.parametrize(
        "orig_type, meta, expect",
        [
            (str, 20, "20s"),
            (str, 1, "1s"),
            (str, 67, "67s"),

            (str, "char", "c"),
            (str, "char[]", "s"),
            (str, "pascal string", "p"),
            (str, "20p", "20p"),
            (str, "2p", "2p"),

            (int, "signed char", "b"),
            (int, "unsigned char", "B"),
            (int, "short", "h"),
            (int, "unsigned short", "H"),
            (int, "int", "i"),
            (int, "unsigned int", "I"),
            (int, "long", "l"),
            (int, "unsigned long", "L"),
            (int, "long long", "q"),
            (int, "unsigned long long", "Q"),

            (float, "float", "f"),
            (float, "double", "d")
        ]
    )
    def test_handle_annotated_type(self,
                                   orig_type: T_AcceptType,
                                   meta: int | str,
                                   expect: str):
        assert Typing_helper.handle_annotated_type(orig_type, meta) == expect

    @pytest.mark.parametrize(
        "orig_type, meta, expect_error_msg",
        [
            pytest.param(
                bool, "...",
                'there is no point in annotating bool',
                id="annotating_bool"
            ),
            pytest.param(
                str, None,
                'str should contain string size in int, c_type or pascal string with size',
                id="wrong_str_annotation"
            ),
            pytest.param(
                str, "",
                "string should not be empty",
                id="empty_annotated_str"
            ),
            pytest.param(
                str, "awd",
                "awd is not valid c_type",
                id="not_existing_c_type"
            ),
            pytest.param(
                NoneType, "",
                'NoneType can not be annotated',
                id="annotated_none"
            ),
            pytest.param(
                int, 67,
                "<class 'int'> should contain c_type information in str",
                id="num_annotated_with_str"
            ),
            pytest.param(
                float, "...",
                "... is not valid c_type",
                id="wrong_type_for_num"
            )
        ]
    )
    def test_handle_annotated_type_errors(self,
                                          orig_type: T_AcceptType,
                                          meta: int | str,
                                          expect_error_msg: str):
        with pytest.raises(InvalidTableError, match=expect_error_msg):
            Typing_helper.handle_annotated_type(orig_type, meta)

    @pytest.mark.parametrize(
        "typ, expect",
        [
            (int, "l"),
            (bool, "?"),
            (float, "d"),
        ]
    )
    def test_handle_type(self, typ: type, expect: str):
        assert Typing_helper.handle_type(typ) == expect

    @pytest.mark.parametrize(
        "type, expect_error_msg",
        [
            pytest.param(
                str,
                'str type is prohibited. Use Annotated from typing module with str',
                id="str_without_annotated"
            ),
            pytest.param(
                NoneType,
                'NoneType can only be second type',
                id="misused_NoneType"
            ),
            pytest.param(
                None,
                'NoneType can only be second type',
                id="misused_NoneType"
            ),
            pytest.param(
                int | float | bool,
                'union type can only be with two types',
                id="3_types"
            ),
            pytest.param(
                int | float,
                'second type can only be None',
                id="misused_second_type"
            ),
            pytest.param(
                bytes,
                "type <class 'bytes'> can not appear",
                id="unsuported_type"
            )
        ]
    )
    def test_handle_type_error(self, type: type, expect_error_msg: str):
        with pytest.raises(InvalidTableError, match=expect_error_msg):
            Typing_helper.handle_type(type)
