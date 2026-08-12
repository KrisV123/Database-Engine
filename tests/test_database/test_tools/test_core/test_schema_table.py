import pytest
from collections.abc import Callable

from database.tools.core.table_schema import get_byte_model_list, get_attr_offset_dict
from database.tools.core.LowBaseModel import LowBaseModel
from database.tools.core.HighBaseModel import HighBaseModel

"""
class Test_get_byte_model_list:

    @pytest.fixture
    def small_class_factory(self) -> Callable[[str], type[LowBaseModel]]:
        def _create(byte_model: str) -> type[LowBaseModel]:

            class Model(HighBaseModel):
                def __init__(self):
                    pass

            cls = Model
            cls.byte_model = byte_model
            return cls

        return _create
    
    @pytest.mark.parametrize(
        "model_str, model_list",
        [
            ('I 20s 20s B', ['I', '20s', '20s', 'B']),
            ('x20s20sB', ['x', '20s', '20s', 'B']),
            ('I20s   20sB', ['I', '20s', '20s', 'B']),
            ('', [])
        ],
        ids=[
            'default',
            'without space',
            'extra_space',
            'empty'
        ]
    )
    def test_get_byte_model_list(self,
                                 model_str: str, model_list: list[str],
                                 small_class_factory: Callable[[str], type[LowBaseModel]]):
        cls = small_class_factory(model_str)
        assert get_byte_model_list(cls.get_table_schema().byte_model) == model_list

    @pytest.mark.parametrize(
        "model_str, error, error_msg",
        [
            ('I 20s s20 B', AttributeError, 'invalid byte model'),
            ('I 20s p B', AttributeError, 'invalid byte model'),
            ('I20ssB', AttributeError, 'invalid byte model')
        ]
    )
    def test_get_byte_model_list_errors(self,
                                        model_str: str, error: type[Exception], error_msg: str,
                                        small_class_factory: Callable[[str], type[LowBaseModel]]):
        cls = small_class_factory(model_str)
        with pytest.raises(error, match=error_msg):
            get_byte_model_list(cls.get_table_schema().byte_model)


class Test_get_offset:
    
    @pytest.mark.parametrize(
            "val, offset", [('email', 54), ('id', 0), ('postal_code', 167)]
    )
    def test_get_offset(self,
                        val: str, offset: int,
                        model_factory_2byte_mask_without_params: Callable):
        cls = model_factory_2byte_mask_without_params()
        order = cls.get_offset(val)
        assert order == offset
"""
