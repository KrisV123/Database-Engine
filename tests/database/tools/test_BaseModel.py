from __future__ import annotations
import pytest #type:ignore[import-not-found]
import struct
from collections.abc import Generator, Callable
import io

from database.tools.BaseModel import LowBaseModel, HighBaseModel, RowList, Table
from tests.database.test_model.test import Test

class Test_RowList:

    @pytest.fixture
    def line_1(self) -> RowList[int | str]:
        return RowList([1, 'Kristian', 'Vesely'], id = 0, Name=1, Surname=2)

    class Test_eq_and_ne_:

        def test_eq_and_ne_sanity(self, line_1: RowList[int | str]):
            expect = RowList[int | str](
                [1, 'Kristian', 'Vesely'],
                id=0, Name=1, Surname=2
            )
            assert list(line_1) == list(expect)
            assert line_1.attributes == expect.attributes
            assert line_1 is not expect
            assert line_1 == expect
            assert not (line_1 != expect)

        def test_eq_and_ne_different_value(self, line_1: RowList[int | str]):
            line_2 = RowList[int | str](
                [1, 'Andrej', 'Mesko'],
                id=0, Name=1, Surname=2
            )
            assert list(line_1) != list(line_2)
            assert line_1.attributes == line_2.attributes
            assert not (line_1 == line_2)
            assert line_1 != line_2

        def test_eq_and_ne_different_attributes(self, line_1: RowList[int | str]):
            line_2 = RowList[int | str](
                [1, 'Kristian', 'Vesely'],
                id=0, Name=1, Country=2
            )
            assert list(line_1) == list(line_2)
            assert line_1.attributes != line_2.attributes
            assert not (line_1 == line_2)
            assert line_1 != line_2

        def test_eq_and_ne_empty_1(self):
            line_1 = RowList()
            line_2 = RowList()
            assert list(line_1) == list(line_2)
            assert line_1.attributes == line_2.attributes
            assert line_1 == line_2
            assert not (line_1 != line_2)

        def test_eq_and_ne_empty_2(self, line_1: RowList):
            line_2 = RowList()
            assert list(line_1) != list(line_2)
            assert line_1.attributes != line_2.attributes
            assert not (line_1 == line_2)
            assert line_1 != line_2

        def test_eq_and_ne_different_obj(self, line_1: RowList):
            line_2: list[object] = list()
            assert list(line_1) != list(line_2)
            assert not (line_1 == line_2)
            assert line_1 != line_2


    class Test_getistem_:

        def test_getitem_key_sanity(self, line_1: RowList):
            assert line_1['id'] == 1
            assert line_1['Name'] == 'Kristian'
            assert line_1['Surname'] == 'Vesely'

            key = 'awdawd'
            with pytest.raises(KeyError, match=key):
                line_1['awdawd']

        def test_getitem_index_sanity(self, line_1: RowList):
            assert line_1[0] == 1
            assert line_1[1] == 'Kristian'
            assert line_1[2] == 'Vesely'

            with pytest.raises(IndexError, match="list index out of range"):
                line_1[3]

        def test_getitem_empty(self, line_1: RowList):
            column_list = RowList()

            assert list(column_list) == list()
            key = 'wdwd'
            with pytest.raises(KeyError, match='wdwd'):
                column_list['wdwd']
            assert column_list.attributes is not None
            with pytest.raises(IndexError, match="list index out of range"):
                column_list[1]


    class Test_setitem_:

        def test_setitem_sanity_1(self, line_1: RowList):
            line_1['id'] = 500
            line_1['Name'] = 'Andrej'
            line_1['Surname'] = 'Mesko'

            assert list(line_1) == [500, 'Andrej', 'Mesko']

        def test_setitem_sanity_2(self, line_1: RowList):
            line_1['Name'] = 'Adam'
            line_1['Surname'] = 'Kocan'

            assert list(line_1) == [1, 'Adam', 'Kocan']

        def test_sanity_key_missing(self, line_1: RowList):
            key = 'awdawd'
            with pytest.raises(KeyError, match=key):
                line_1[key] = 5000


    class Test_add:

        def test_add_sanity(self, line_1: RowList):
            line_2 = RowList(
                ['Czechia', 'male'],
                Country=0, Gender=1
            )
            attribs = {'id': 0, 'Name': 1, 'Surname': 2, 'Country': 3, 'Gender': 4}
            expect = RowList([1, 'Kristian', 'Vesely', 'Czechia', 'male'])
            expect._attributes = attribs

            attribs_reverse = {'Country': 0, 'Gender': 1, 'id': 2, 'Name': 3, 'Surname': 4}
            expect_reverse = RowList(['Czechia', 'male', 1, 'Kristian', 'Vesely'])
            expect_reverse._attributes = attribs_reverse

            summ = line_1 + line_2
            assert list(summ) == list(expect)
            assert summ.attributes == attribs

            summ_reverse = line_2 + line_1
            assert list(summ_reverse) == list(expect_reverse)
            assert summ_reverse.attributes == attribs_reverse

        def test_add_empty(self, line_1: RowList):
            empty_line = RowList()

            assert line_1 + empty_line == line_1
            assert empty_line + line_1 == line_1
            assert empty_line + empty_line == empty_line

        def test_add_non_copatible(self,  line_1: RowList):
            llist: list[object] = list()
            with pytest.raises(TypeError, match="only two RowLists can be summed"):
                summ = line_1 + llist #type:ignore


    class Test_append_named:

        def test_append_named_sanity(self, line_1: RowList):
            line = line_1.copy()
            line.append_named('Slovakia', 'Country')
            line.append_named('0908_425_865', 'Phone_num')

            expect = RowList(list(line_1) + ['Slovakia', '0908_425_865'],
                                **(line_1.attributes | {'Country': 3, 'Phone_num': 4}))
            assert list(line) == list(expect)
            assert line.attributes == expect.attributes

        def test_append_named_empty_list(self):
            empty_line = RowList()
            empty_line.append_named('Slovakia', 'Country')
            expect = RowList(['Slovakia'], Country=0)

            assert list(empty_line) == list(expect)
            assert empty_line.attributes == expect.attributes


    class Test_pop_named:

        def test_pop_named_last(self, line_1: RowList):
            line = line_1.copy()
            line.pop_named('Surname')

            expect_attrs = line_1.attributes
            expect_attrs.pop('Surname')
            expect = RowList(list(line_1)[:-1], **expect_attrs)

            assert list(line) == list(expect)
            assert line.attributes == expect.attributes

        def test_pop_named_middle(self, line_1: RowList):
            line = line_1.copy()
            line.pop_named('Name')

            expect_attrs = {'id': 0, 'Surname': 1}
            expect_values = list(line_1).copy()
            expect_values.pop(1)
            expect = RowList(expect_values, **expect_attrs)

            assert list(line) == list(expect)
            assert line.attributes == expect.attributes

        def test_pop_named_first(self, line_1: RowList):
            line = line_1.copy()
            line.pop_named('id')

            expect_attrs = {'Name': 0, 'Surname': 1}
            expect_values = list(line_1).copy()
            expect_values.pop(0)
            expect = RowList(expect_values, **expect_attrs)

            assert list(line) == list(expect)
            assert line.attributes == expect.attributes

        def test_pop_named_missing_attribute(self, line_1: RowList):
            attr_name = 'awdawd'
            with pytest.raises(KeyError,
                               match=f"attribute '{attr_name}' not inside RowList"):
                line_1.pop_named(attr_name)


    class Test_copy:

        def test_copy_sanity(self, line_1: RowList):
            copy_line = line_1.copy()

            assert list(line_1) == list(copy_line)
            assert list(line_1) is not list(copy_line)

            assert line_1.attributes == copy_line.attributes
            assert line_1.attributes is not copy_line.attributes

            assert line_1 == copy_line
            assert line_1 is not copy_line

            assert line_1[0] is copy_line[0]
            assert line_1.attributes['Name'] is copy_line.attributes['Name']


class Test_Table:

    QuadRowList = tuple[
        RowList[int | str | None],
        RowList[int | str | None],
        RowList[int | str | None],
        RowList[int | str | None]
    ]

    @pytest.fixture
    def meta_model(self) -> QuadRowList:
        attrs = {
            'id': 0, 'name': 1, 'surname': 2, 'birth_date': 3,
            'email': 4, 'phone_num': 5
        }
        model_1= RowList[int | str | None]([
            1, 'Kristian', 'Vesely', '20.01.2001',
            'kris.v@gmail.com', None],
            **attrs
        )
        model_2= RowList[int | str | None]([
            2, 'Jozko', 'Mrkvicka', '25.05.2514',
            'jozko.m@gmail.com', None],
            **attrs
        )
        model_3= RowList[int | str | None]([
            3, 'Andrej', 'Mesko', None,
            'andrewmes007@gmail.com', '2564_568_524'],
            **attrs
        )
        model_4= RowList[int | str | None]([
            4, 'Andrej', 'Mesko', None,
            None, '1234_567_890'],
            **attrs
        )
        return (model_1, model_2, model_3, model_4)


    class Test_eq_and_ne_:

        def test_eq_and_ne_sanity(self, meta_model: Test_Table.QuadRowList):
            table_1 = Table({(model['id'], ): model
                             for model in meta_model},
                            **meta_model[0].attributes)
            table_2 = Table({(model['id'], ): model
                             for model in meta_model},
                            **meta_model[0].attributes)

            assert dict(table_1) == dict(table_2)
            assert table_1.attributes == table_2.attributes
            assert table_1 is not table_2
            assert table_1 == table_2
            assert not (table_1 != table_2)

        def test_eq_and_ne_different_values(self, meta_model: Test_Table.QuadRowList):
            table_1 = Table({(model['id'], ): model
                             for model in meta_model},
                            **meta_model[0].attributes)
            table_2 = Table({(model['id'], ): model
                             for model in meta_model[:-1]},
                            **meta_model[0].attributes)

            assert dict(table_1) != dict(table_2)
            assert table_1.attributes == table_2.attributes
            assert table_1 is not table_2
            assert not (table_1 == table_2)
            assert table_1 != table_2

        def test_eq_and_ne_different_attributes(self, meta_model: Test_Table.QuadRowList):
            table_1 = Table({(model['id'], ): model
                             for model in meta_model},
                            **meta_model[0].attributes)
            table_2 = Table({(model['id'], ): model
                             for model in meta_model},
                            **{'param_1': 1, 'param_2': 2})

            assert dict(table_1) == dict(table_2)
            assert table_1.attributes != table_2.attributes
            assert table_1 is not table_2
            assert not (table_1 == table_2)
            assert table_1 != table_2


    class Test_project:

        def test_project_default(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model['id'],): model
                                for model in meta_model},
                               **meta_model[0].attributes)

            expect_attrs = {'name': 0, 'surname': 1}

            expect = Table({
                (model['id'],): RowList([model['name'], model['surname']],
                                           **expect_attrs)
                 for model in meta_model},
                **expect_attrs)

            project_table = dict_model.project('name', 'surname')

            assert dict(expect) == dict(project_table)
            assert expect.attributes == project_table.attributes

        def test_project_empty(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model['id'],): model
                                for model in meta_model},
                               **meta_model[0].attributes)

            expect = Table({(model[0],): RowList() for model in meta_model})
            project_table = dict_model.project()

            assert dict(expect) == dict(project_table)
            assert expect.attributes == project_table.attributes

        def test_project_index(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model['id'],): model
                                for model in meta_model},
                               **meta_model[0].attributes)
            expect_attrs = {'id': 0, 'name': 1, 'surname': 2}
            expect = Table({
                (model['id'],): RowList([model[0], model[1], model[2]], **expect_attrs)
                for model in meta_model},
                **expect_attrs)

            project_table = dict_model.project(0, 1, 2)

            assert dict(expect) == dict(project_table)
            assert expect.attributes == project_table.attributes

        def test_project_wrong_attr(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model['id'],): model
                                for model in meta_model},
                               **meta_model[0].attributes)
            key = "awdawd"
            with pytest.raises(KeyError, match=key):
                dict_model.project('awdawd')


    class Test_select:

        def test_select_default_1(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model['id'],): model
                                for model in meta_model},
                               **meta_model[0].attributes)
            expect = Table({(model['id'],): model
                            for model in meta_model
                            if model['name'] == 'Kristian'},
                           **meta_model[0].attributes)

            select_table = dict_model.select("name == 'Kristian'")

            assert dict(expect) == dict(select_table)
            assert expect.attributes == select_table.attributes

        def test_select_default_2(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model['id'],): model
                                for model in meta_model},
                               **meta_model[0].attributes)
            expect = Table({(model['id'],): model
                            for model in meta_model
                            if model['name'] == 'Kristian' or\
                               model['name'] == 'Andrej'},
                           **meta_model[0].attributes)

            select_table = dict_model.select("name == 'Kristian' or name == 'Andrej'")

            assert dict(expect) == dict(select_table)
            assert expect.attributes == select_table.attributes

        def test_select_empty(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model['id'],): model
                                for model in meta_model},
                               **meta_model[0].attributes)
            expect = Table(dict(), **meta_model[0].attributes)

            select_table = dict_model.select("surname == 'wdwdwd'")

            assert dict(expect) == dict(select_table)
            assert expect.attributes == select_table.attributes


    class Test_union:

        def test_union_default_1(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model[0],): RowList(model)
                                for model in meta_model},
                               **meta_model[0].attributes)

            addition: dict[
                tuple[int | str | None],
                RowList[int | str | None]
            ] = {
                (6,): RowList([
                6, 'David', 'Guetta', None,
                'david.guetta@gmail.com', '1234_567_890']
            )}
            attributes = {
                'id': 0, 'name': 1, 'surname': 2, 'birth_date': 3,
                'email': 4, 'phone_num': 5
            }
            new_dict = Table(addition, **attributes)

            expect = {(model[0],): RowList(model)
                      for model in meta_model}
            expect |= addition
            expect = Table(expect, **attributes)

            union_table = dict_model.union(new_dict)

            assert dict(expect) == dict(union_table)
            assert expect.attributes == union_table.attributes

        def test_union_default_2(self, meta_model: Test_Table.QuadRowList):
            addition: dict[
                tuple[int | str | None],
                RowList[int | str | None]
            ] = {
                (6,): RowList([
                    6, 'David', 'Guetta', None,
                    'david.guetta@gmail.com', '1234_567_890']
                ),
                (7,): RowList([
                    7, 'Martin', 'Garrix', None,
                    None, '1234_567_890'])
            }
            attributes = {
                'id': 0, 'name': 1, 'surname': 2, 'birth_date': 3,
                'email': 4, 'phone_num': 5
            }

            dict_model = Table({(model[0],): RowList(model)
                                for model in meta_model},
                               **meta_model[0].attributes)
            new_dict = Table(addition, **attributes)

            expect = {(model[0],): RowList(model)
                      for model in meta_model}
            expect |= addition
            expect = Table(expect, **attributes)

            union_table = dict_model.union(new_dict)

            assert dict(expect) == dict(union_table)
            assert expect.attributes == union_table.attributes

        def test_union_empty(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model[0],): RowList(model)
                                for model in meta_model},
                               **meta_model[0].attributes)
            attributes = {
                'id': 0, 'name': 1, 'surname': 2, 'birth_date': 3,
                'email': 4, 'phone_num': 5
            }
            new_dict = Table[int | str | None](dict(), **attributes)

            union_dict = dict_model.union(new_dict)

            assert dict(union_dict) == dict(dict_model)
            assert union_dict.attributes == dict_model.attributes

        def test_union_empty_reverse(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model[0],): RowList(model)
                                for model in meta_model},
                               **meta_model[0].attributes)
            attributes = {
                'id': 0, 'name': 1, 'surname': 2, 'birth_date': 3,
                'email': 4, 'phone_num': 5
            }
            new_dict = Table[int | str | None](dict(), **attributes)

            union_dict = new_dict.union(dict_model)

            assert dict(union_dict) == dict(dict_model)
            assert union_dict.attributes == dict_model.attributes

        def test_union_diff_attribs(self, meta_model: Test_Table.QuadRowList):
            dict_model = Table({(model[0],): RowList(model)
                                for model in meta_model},
                               **meta_model[0].attributes)

            attributes = {
                'id': 0, 'name': 1, 'surname': 2, 'birth_date': 3,
                'email': 4, 'phone_num': 5
            }
            column = RowList[int | str | None]([
                6, 'David', 'Guetta', None,
                'davig.guetta@gmail.com', '1234_567_890'],
                **attributes)

            column.append_named(True, 'valid')
            addition: dict[
                tuple[int | str | None],
                RowList[int | str | None]
            ] = {(column[0],): column}

            new_dict = Table(addition, **attributes | {'valid': 6})

            expect = {(model[0],): RowList(model)
                      for model in meta_model}
            expect |= addition
            expect = Table(expect, **meta_model[0].attributes)

            with pytest.raises(AttributeError, match="attributes from tables don't match"):
                dict_model.union(new_dict)


    class Test_difference:

        def test_difference_sanity(self):
            attribs = {'id': 0, 'name': 1}
            column_1_1 = RowList([0, 'Kristian'], **attribs)
            column_1_2 = RowList([1, 'Andrej'], **attribs)
            table_1 = Table({
                (column_1_1[0],): column_1_1,
                (column_1_2[0],): column_1_2},
                **attribs)

            column_2_1 = RowList([0, 'Kristian'], **attribs)
            column_2_2 = RowList([1, 'Adam'], **attribs)
            table_2 = Table({
                (column_2_1[0],): column_2_1,
                (column_2_2[0],): column_2_2},
                **attribs)

            expect = Table(
                {(1,): RowList([1, 'Andrej'], **attribs)},
                **attribs)

            difference_table = table_1.difference(table_2)

            assert dict(difference_table) == dict(expect)
            assert difference_table.attributes == expect.attributes

        def test_difference_sanity_2(self):
            attribs = {'id': 0, 'Name': 1, 'Surname': 2}

            column_1_1 = RowList([1, 'Andrej', 'Meško'], **attribs)
            column_1_2 = RowList([2, 'Kristian', 'Vesely'], **attribs)
            column_1_3 = RowList([3, 'Adam', 'Kocan'], **attribs)
            column_1_4 = RowList([4, 'Jozko', 'Mrkvicka'], **attribs)
            column_1_5 = RowList([5, 'Janko', 'Hrasko'], **attribs)
            table_1 = Table({
                (column_1_1[0],): column_1_1,
                (column_1_2[0],): column_1_2,
                (column_1_3[0],): column_1_3,
                (column_1_4[0],): column_1_4,
                (column_1_5[0],): column_1_5},
                **attribs)

            column_2_1 = RowList([1, 'Andrej', 'Meško'], **attribs)
            column_2_2 = RowList([5, 'Kristian', 'Vesely'], **attribs)
            column_2_3 = RowList([6, 'Adam', 'Kocan'], **attribs)
            column_2_4 = RowList([4, 'Jozko', 'Mrkvicka'], **attribs)
            column_2_5 = RowList([5, 'Janko', 'Hrasko'], **attribs)
            table_2 = Table({
                (column_2_1[0],): column_2_1,
                (column_2_2[0],): column_2_2,
                (column_2_3[0],): column_2_4,
                (column_2_4[0],): column_2_4,
                (column_2_5[0],): column_2_5},
                **attribs)

            expect = Table({
                (2,): RowList([2, 'Kristian', 'Vesely'], **attribs),
                (3,): RowList([3, 'Adam', 'Kocan'], **attribs)},
                **attribs)

            difference_table = table_1.difference(table_2)

            assert dict(difference_table) == dict(expect)
            assert difference_table.attributes == expect.attributes

        def test_difference_not_union(self):
            attribs = {'id': 0, 'name': 1}
            column_1_1 = RowList([0, 'Jozko'], **attribs)
            column_1_2 = RowList([1, 'Andrej'], **attribs)
            table_1 = Table({
                (column_1_1[0],): column_1_1,
                (column_1_2[0],): column_1_2},
                **attribs)

            column_2_1 = RowList([0, 'Kristian'], **attribs)
            column_2_2 = RowList([1, 'Adam'], **attribs)
            table_2 = Table({
                (column_2_1[0],): column_2_1,
                (column_2_2[0],): column_2_2},
                **attribs)

            difference_table = table_1.difference(table_2)

            assert dict(difference_table) == dict(table_1)
            assert difference_table.attributes == table_1.attributes

        def test_difference_delete_all(self):
            attribs = {'id': 0, 'name': 1}
            column_1_1 = RowList([0, 'Kristian'], **attribs)
            column_1_2 = RowList([1, 'Andrej'], **attribs)

            table_1 = Table({
                (column_1_1[0],): column_1_1,
                (column_1_2[0],): column_1_2},
                **attribs)
            table_2 = Table({
                (column_1_1[0],): column_1_1,
                (column_1_2[0],): column_1_2},
                **attribs)

            expect = Table(dict(), **attribs)
            difference_table = table_1.difference(table_2)

            assert dict(difference_table) == dict(expect)
            assert difference_table.attributes == expect.attributes

        def test_difference_wrong_attrs(self):
            attribs_1 = {'id': 0, 'name': 1}
            column_1_1 = RowList([0, 'Kristian'], **attribs_1)
            table_1 = Table({(column_1_1[0],): column_1_1}, **attribs_1)

            attribs_2 = {'id': 0, 'nick': 1}
            column_2_1 = RowList([0, 'Kristian'], **attribs_2)
            table_2 = Table({(column_2_1[0],): column_2_1},**attribs_2)

            with pytest.raises(AttributeError, match = "attributes from tables don't match"):
                table_1.difference(table_2)

        def test_difference_line_attrs(self):
            attribs = {'id': 0, 'name': 1}
            column_1_1 = RowList([0, 'Kristian'], **attribs)
            column_1_2 = RowList([1, 'Andrej'], **attribs)

            table_1 = Table({
                (column_1_1[0],): column_1_1,
                (column_1_2[0],): column_1_2},
                **attribs)
            table_2 = Table({(column_1_1[0],): column_1_1}, **attribs)

            difference_table = table_1.difference(table_2)

            assert difference_table[(1,)].attributes == difference_table.attributes

        def test_difference_left_empty_table(self):
            attribs = {'id': 0, 'name': 1}
            column_2_1 = RowList([0, 'Kristian'], **attribs)
            column_2_2 = RowList([1, 'Andrej'], **attribs)

            table_1 = Table[int | str](dict(), **attribs)
            table_2 = Table({
                (column_2_1[0],): column_2_1,
                (column_2_2[0],): column_2_2},
                **attribs)

            expect = Table(dict(), **attribs)
            difference_table = table_1.difference(table_2)

            assert dict(difference_table) == dict(expect)
            assert difference_table.attributes == expect.attributes

        def test_difference_right_empty_table(self):
            attribs = {'id': 0, 'name': 1}
            column_2_1 = RowList([0, 'Kristian'], **attribs)
            column_2_2 = RowList([1, 'Andrej'], **attribs)

            table_1 = Table[int | str](dict(), **attribs)
            table_2 = Table({
                (column_2_1[0],): column_2_1,
                (column_2_2[0],): column_2_2},
                **attribs)

            expect = table_2
            difference_table = table_2.difference(table_1)

            assert dict(difference_table) == dict(expect)
            assert difference_table.attributes == expect.attributes


    class Test_join:

        @pytest.fixture
        def table_1(self) -> Table[int | str]:
            attribs = {'id': 0, 'Name': 1, 'Surname': 2}

            column_1_1 = RowList[int | str]([1, 'Andrej', 'Meško'], **attribs)
            column_1_2 = RowList[int | str]([2, 'Kristian', 'Vesely'], **attribs)
            column_1_3 = RowList[int | str]([3, 'Adam', 'Kocan'], **attribs)
            column_1_4 = RowList[int | str]([4, 'Jozko', 'Mrkvicka'], **attribs)

            return Table({
                (column_1_1[0],): column_1_1,
                (column_1_2[0],): column_1_2,
                (column_1_3[0],): column_1_3,
                (column_1_4[0],): column_1_4},
                **attribs)

        @pytest.fixture
        def table_2(self) -> Table[int]:
            attribs = {'id': 0, 'Sallery': 1}

            column_2_1 = RowList[int]([1, 5000], **attribs)
            column_2_2 = RowList[int]([1, 8000], **attribs)
            column_2_3 = RowList[int]([4, 20000], **attribs)
            column_2_4 = RowList[int]([5, 15000], **attribs)

            return Table({
                (tuple(column_2_1)): column_2_1,
                (tuple(column_2_2)): column_2_2,
                (tuple(column_2_3)): column_2_3,
                (tuple(column_2_4)): column_2_4},
                **attribs)

        def test_inner_join_sanity(self, table_1: Table, table_2: Table):
            join_table = table_1.join('INNER', table_2, 'id')

            expect_attrs = {'Name': 0, 'Surname': 1, 'Sallery': 2}
            expect = Table({
                (1, 1, 5000): RowList(['Andrej', 'Meško', 5000], **expect_attrs),
                (1, 1, 8000): RowList(['Andrej', 'Meško', 8000], **expect_attrs),
                (4, 4, 20000): RowList(['Jozko', 'Mrkvicka', 20000], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_inner_join_sanity_reverse(self, table_1: Table, table_2: Table):
            join_table = table_2.join('INNER', table_1, 'id')

            expect_attrs = {'Sallery': 0, 'Name': 1, 'Surname': 2}
            expect = Table({
                (1, 5000, 1): RowList([5000, 'Andrej', 'Meško'], **expect_attrs),
                (1, 8000, 1): RowList([8000, 'Andrej', 'Meško'], **expect_attrs),
                (4, 20000, 4): RowList([20000, 'Jozko', 'Mrkvicka'], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_left_join_sanity(self, table_1: Table, table_2: Table):
            join_table = table_1.join('LEFT', table_2, 'id')

            expect_attrs = {'id.1': 0, 'Name': 1, 'Surname': 2, 'id.2': 3, 'Sallery': 4}
            expect = Table[int | str | None]({
                (0,): RowList([1, 'Andrej', 'Meško', 1, 5000], **expect_attrs),
                (1,): RowList([1, 'Andrej', 'Meško', 1, 8000], **expect_attrs),
                (2,): RowList([2, 'Kristian', 'Vesely', None, None], **expect_attrs),
                (3,): RowList([3, 'Adam', 'Kocan', None, None], **expect_attrs),
                (4,): RowList([4, 'Jozko', 'Mrkvicka', 4, 20000], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_left_join_sanity_reverse(self, table_1: Table, table_2: Table):
            join_table = table_2.join('LEFT', table_1, 'id')

            # tables are reversed, so indexes are properly set besides tables variable name
            expect_attrs = {'id.1': 0, 'Sallery': 1, 'id.2': 2, 'Name': 3, 'Surname': 4}
            expect = Table[int | str | None]({
                (0,): RowList([1, 5000, 1, 'Andrej', 'Meško'], **expect_attrs),
                (1,): RowList([1, 8000, 1, 'Andrej', 'Meško'], **expect_attrs),
                (2,): RowList([4, 20000, 4, 'Jozko', 'Mrkvicka'], **expect_attrs),
                (3,): RowList([5, 15000, None, None, None], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_right_join_sanity(self, table_1: Table, table_2: Table):
            join_table = table_1.join('RIGHT', table_2, 'id')
            expect_attrs = {'id.1': 0, 'Name': 1, 'Surname': 2, 'id.2': 3, 'Sallery': 4}
            expect = Table[int | str | None]({
                (0,): RowList([1, 'Andrej', 'Meško', 1, 5000], **expect_attrs),
                (1,): RowList([1, 'Andrej', 'Meško', 1, 8000], **expect_attrs),
                (2,): RowList([4, 'Jozko', 'Mrkvicka', 4, 20000], **expect_attrs),
                (3,): RowList([None, None, None, 5, 15000], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_right_join_sanity_reverse(self, table_1: Table, table_2: Table):
            join_table = table_2.join('RIGHT', table_1, 'id')

            # tables are reversed, so indexes are properly set besides tables variable name
            expect_attrs = {'id.1': 0, 'Sallery': 1, 'id.2': 2, 'Name': 3, 'Surname': 4}
            expect = Table[int | str | None]({
                (0,): RowList([1, 5000, 1, 'Andrej', 'Meško'], **expect_attrs),
                (1,): RowList([1, 8000, 1, 'Andrej', 'Meško'], **expect_attrs),
                (2,): RowList([4, 20000, 4, 'Jozko', 'Mrkvicka'], **expect_attrs),
                (3,): RowList([None, None, 2, 'Kristian', 'Vesely'], **expect_attrs),
                (4,): RowList([None, None, 3, 'Adam', 'Kocan'], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        @pytest.fixture
        def multi_key_table(self) -> Table[str]:
            attribs = {'Name': 0, 'Surname': 1, 'Country': 2}

            column_1 = RowList[str](['Andrej', 'Meško', 'Switzerland'], **attribs)
            column_2 = RowList[str](['Kristian', 'Vesely', 'Czechia'], **attribs)
            column_3 = RowList[str](['Adam', 'Kocan', 'Slovakia'], **attribs)

            return Table({
                (column_1[0], column_1[1]): column_1,
                (column_2[0], column_2[1]): column_2,
                (column_3[0], column_3[1]): column_3},
                **attribs)

        def test_join_multi_primary_key_inner(self, table_1: Table,
                                              multi_key_table: Table):
            table_2 = multi_key_table
            join_table = table_1.join('INNER', table_2, 'Name', 'Surname')

            expect_attrs = {'id': 0, 'Country': 1}
            expect = Table({
                (1, 'Andrej', 'Meško'): RowList([1, 'Switzerland'], **expect_attrs),
                (2, 'Kristian', 'Vesely'): RowList([2, 'Czechia'], **expect_attrs),
                (3, 'Adam', 'Kocan'): RowList([3, 'Slovakia'], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_join_multi_primary_key_left(self, table_1: Table,
                                             multi_key_table: Table):
            table_2 = multi_key_table

            join_table = table_1.join('LEFT', table_2, 'Name', 'Surname')

            expect_attrs = {
                'id': 0, 'Name.1': 1, 'Surname.1': 2,
                'Name.2': 3, 'Surname.2': 4, 'Country': 5
            }
            expect = Table[int | str | None]({
                (0,): RowList([1, 'Andrej', 'Meško', 'Andrej', 'Meško', 'Switzerland'], **expect_attrs),
                (1,): RowList([2, 'Kristian', 'Vesely', 'Kristian', 'Vesely', 'Czechia'], **expect_attrs),
                (2,): RowList([3, 'Adam', 'Kocan', 'Adam', 'Kocan', 'Slovakia'], **expect_attrs),
                (3,): RowList([4, 'Jozko', 'Mrkvicka', None, None, None], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_join_multi_primary_key_right(self, table_1: Table,
                                              multi_key_table: Table):
            table_2 = multi_key_table
            join_table = table_1.join('RIGHT', table_2, 'Name', 'Surname')

            expect_attrs = {
                'id': 0, 'Name.1': 1, 'Surname.1': 2,
                'Name.2': 3, 'Surname.2': 4, 'Country': 5
            }
            expect = Table({
                (0,): RowList([1, 'Andrej', 'Meško', 'Andrej', 'Meško', 'Switzerland'], **expect_attrs),
                (1,): RowList([2, 'Kristian', 'Vesely', 'Kristian', 'Vesely', 'Czechia'], **expect_attrs),
                (2,): RowList([3, 'Adam', 'Kocan', 'Adam', 'Kocan', 'Slovakia'], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_join_inner_empty_table(self, table_1: Table):
            table_2 = Table(dict(), **{'id': 0, 'Country': 1})
            join_table = table_1.join('INNER', table_2, 'id')

            expect_attributes = {'Name': 0, 'Surname': 1, 'Country': 2}
            expect = Table(dict(), **expect_attributes)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_join_left_empty_table(self, table_1: Table):
            table_2 = Table(dict(), **{'id': 0, 'Country': 1})
            join_table = table_1.join('LEFT', table_2, 'id')

            expect_attrs = {'id.1': 0, 'Name': 1, 'Surname': 2, 'id.2': 3, 'Country': 4}
            expect = Table({
                (0,): RowList([1, 'Andrej', 'Meško', None, None], **expect_attrs),
                (1,): RowList([2, 'Kristian', 'Vesely', None, None], **expect_attrs),
                (2,): RowList([3, 'Adam', 'Kocan', None, None], **expect_attrs),
                (3,): RowList([4, 'Jozko', 'Mrkvicka', None, None], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_join_right_empty_table(self, table_1: Table):
            table_2 = Table(dict(), **{'id': 0, 'Country': 1})

            join_table = table_1.join('RIGHT', table_2, 'id')

            expect_attributes = {'id.1': 0, 'Name': 1, 'Surname': 2, 'id.2': 3, 'Country': 4}
            expect = Table(dict(), **expect_attributes)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes

        def test_join_right_empty_table_reverse(self, table_1: Table):
            table_2 = Table(dict(), **{'id': 0, 'Country': 1})

            join_table = table_2.join('RIGHT', table_1, 'id')

            expect_attrs = {'id.1': 0, 'Country': 1, 'id.2': 2, 'Name': 3, 'Surname': 4}
            expect = Table({
                (0,): RowList([None, None, 1, 'Andrej', 'Meško'], **expect_attrs),
                (1,): RowList([None, None, 2, 'Kristian', 'Vesely'], **expect_attrs),
                (2,): RowList([None, None, 3, 'Adam', 'Kocan'], **expect_attrs),
                (3,): RowList([None, None, 4, 'Jozko', 'Mrkvicka'], **expect_attrs)},
                **expect_attrs)

            assert dict(join_table) == dict(expect)
            assert join_table.attributes == expect.attributes


class Test_LowBaseModel():

    class Test_get_packer:

        @pytest.fixture
        def inst(self) -> Generator[LowBaseModel, None, None]:
            state = LowBaseModel()
            yield state
            del state

        def test_get_packer_default(self, inst: LowBaseModel):
            assert inst._packer is None
            inst.get_packer()
            assert inst._packer is not None

        def test_get_packer_type(self, inst: LowBaseModel):
            resp = inst.get_packer()
            assert isinstance(resp, struct.Struct)

        def test_get_packer_equality(self, inst: LowBaseModel):
            """firstly check if it is even equivalent"""

            resp1 = inst.get_packer()
            resp2 = inst.get_packer()
            assert resp1 == resp2

        def test_get_packer_identity(self, inst: LowBaseModel):
            """next if it identical"""

            resp1 = inst.get_packer()
            resp2 = inst.get_packer()
            assert resp1 is resp2


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
    def model_factory_default_with_params(self) -> Callable:
        def _create(id: int, name: str, surname: str, birth_date: str,
                    email: str, phone_num: str):

            class Model(HighBaseModel):
                byte_model = 'I 20s 20s 10s 40s 13s'

                def __init__(self,
                             id: int,
                             name: str,
                             surname: str,
                             birth_date: str | None,
                             email: str | None = None,
                             phone_num: str | None = None):
                    self.id = id
                    self.name = name
                    self.surname = surname
                    self.birth_date = birth_date
                    self.email = email
                    self.phone_num = phone_num

            return Model(id, name, surname, birth_date, email, phone_num)
        return _create

    @pytest.fixture
    def model_factory_2byte_mask(self) -> Callable:
        def _create(id, name, surname, birth_date, email,
                    phone_num, adress, city, postal_code):

            class Model(HighBaseModel):
                byte_model = 'I 20s 20s 10s 40s 13s 40s 20s 6s'

                def __init__(self,
                             id: int,
                             name: str,
                             surname: str,
                             birth_date: str | None,
                             email: str | None = None,
                             phone_num: str | None = None,
                             address: str | None = None,
                             city: str | None = None,
                             postal_code: str | None = None):
                    self.id = id
                    self.name = name
                    self.surname = surname
                    self.birth_date = birth_date
                    self.email = email
                    self.phone_num = phone_num
                    self.address = address
                    self.city = city
                    self.postal_code = postal_code

            return Model(id, name, surname, birth_date, email,
                         phone_num, adress, city, postal_code)
        return _create

    @pytest.fixture
    def small_class_factory(self) -> Callable:
        def _create():
            class Model(HighBaseModel):
                byte_model = 'I 20s 20s'
                __slots__ = ['id', 'name', 'surname']
                path = io.BytesIO(bytes([0b00111110, 0b01111111, 0b11000000])) #type:ignore

                def __init__(self,
                             id: int | None,
                             name: str | None,
                             surname: str):
                    self.id = id
                    self.name = name
                    self.surname = surname

            return Model
        return _create

    @pytest.fixture
    def model_factory_2byte_mask_without_params(self) -> Callable:
        def _create():
            class Model(HighBaseModel):
                byte_model = 'I 20s 20s 10s 40s 13s 40s 20s 6s'

                def __init__(self,
                             id: int,
                             name: str,
                             surname: str,
                             birth_date: str | None,
                             email: str | None = None,
                             phone_num: str | None = None,
                             address: str | None = None,
                             city: str | None = None,
                             postal_code: str | None = None):
                    self.id = id
                    self.name = name
                    self.surname = surname
                    self.birth_date = birth_date
                    self.email = email
                    self.phone_num = phone_num
                    self.address = address
                    self.city = city
                    self.postal_code = postal_code

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
                                model.placeholder['bytes'] * 10,
                                model.placeholder['bytes'] * 40,
                                model.placeholder['bytes'] * 13
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
                                    model.placeholder['bytes'] * 20,
                                    model.placeholder['bytes'] * 6
                                   )

            assert len(expect) == len(model.getstate())
            assert expect == model.getstate()

        @pytest.fixture
        def model_factory_empty(self):

            class Model(HighBaseModel):
                byte_model = ''

                def __init__(self):
                    pass

            return Model()

        def test_getstate_empty_class(self, model_factory_empty):
            model = model_factory_empty
            expect = b''

            assert len(expect) == len(model.getstate())
            assert expect == model.getstate()


    class Test_setstate:

        def test_setstate_default(self, small_class_factory):
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

            assert len(bstream) == cls.inst_len()

            inst = cls.setstate(bstream)

            assert inst.id == data[0]
            assert inst.name == data[1]
            assert inst.surname == data[2]

        def test_setstate_none_values(self, small_class_factory):
            data = (None, None, None)
            cls = small_class_factory()

            bstream = (
                bytes([0b11100000])
                + struct.pack('I', cls.placeholder['int'])
                + 2 * (cls.placeholder['bytes'] * 20)
            )

            assert len(bstream) == cls.inst_len()

            inst = cls.setstate(bstream)

            assert inst.id == data[0]
            assert inst.name == data[1]
            assert inst.surname == data[2]

        def test_setstate_2bytes_prefix(self,
                                        model_factory_2byte_mask_without_params):
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
            assert len(bstream) == cls.inst_len()

            inst = cls.setstate(bstream)

            for idx, attr in enumerate(cls.__slots__):
                assert data[idx] == getattr(inst, attr)


    class Test_get_byte_model_list:

        @pytest.fixture
        def small_class_factory(self) -> Callable:
            def _create(byte_model: str):

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
            assert cls.get_byte_model_list() == model_list

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
                cls.get_byte_model_list()


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
            inst_len = Test.inst_len()
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


class Test_HighBaseModel:

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

            inst_len = Test.inst_len()
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

            inst_len = Test.inst_len()
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
    def db_attribs(self) -> dict[str, int]:
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
            expect_attrs = {attr: idx for idx, attr in enumerate(Test.__slots__)} #type: ignore[attr-defined]
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

            meta = (model_1, model_2, model_3, model_4)
            return meta

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
