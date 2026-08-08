from __future__ import annotations
import pytest #type:ignore[import-not-found]

from database.tools.core.table import Table
from database.tools.core.row import RowList

QuadRowList = tuple[
    RowList[int | str | None],
    RowList[int | str | None],
    RowList[int | str | None],
    RowList[int | str | None]
]

@pytest.fixture
def meta_model() -> QuadRowList:
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

    def test_eq_and_ne_sanity(self, meta_model: QuadRowList):
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

    def test_eq_and_ne_different_values(self, meta_model: QuadRowList):
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

    def test_eq_and_ne_different_attributes(self, meta_model: QuadRowList):
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

    def test_project_default(self, meta_model: QuadRowList):
        dict_model = Table({(model['id'],): model
                            for model in meta_model},
                            **meta_model[0].attributes)

        expect_attrs = {'name': 0, 'surname': 1}

        expect = Table({
            (model['id'],): RowList(
                [model['name'], model['surname']], **expect_attrs
            )
            for model in meta_model},
            **expect_attrs)

        project_table = dict_model.project('name', 'surname')

        assert dict(expect) == dict(project_table)
        assert expect.attributes == project_table.attributes

    def test_project_empty(self, meta_model: QuadRowList):
        dict_model = Table({(model['id'],): model
                            for model in meta_model},
                            **meta_model[0].attributes)

        expect = Table({(model[0],): RowList() for model in meta_model})
        project_table = dict_model.project()

        assert dict(expect) == dict(project_table)
        assert expect.attributes == project_table.attributes

    def test_project_index(self, meta_model: QuadRowList):
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

    def test_project_wrong_attr(self, meta_model: QuadRowList):
        dict_model = Table({(model['id'],): model
                            for model in meta_model},
                            **meta_model[0].attributes)
        key = "awdawd"
        with pytest.raises(KeyError, match=key):
            dict_model.project('awdawd')


class Test_select:

    def test_select_default_1(self, meta_model: QuadRowList):
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

    def test_select_default_2(self, meta_model: QuadRowList):
        dict_model = Table({(model['id'],): model
                            for model in meta_model},
                            **meta_model[0].attributes)
        expect = Table({(model['id'],): model
                        for model in meta_model
                        if (model['name'] == 'Kristian' or
                            model['name'] == 'Andrej')},
                        **meta_model[0].attributes)

        select_table = dict_model.select("name == 'Kristian' or name == 'Andrej'")

        assert dict(expect) == dict(select_table)
        assert expect.attributes == select_table.attributes

    def test_select_empty(self, meta_model: QuadRowList):
        dict_model = Table({(model['id'],): model
                            for model in meta_model},
                            **meta_model[0].attributes)
        expect = Table(dict(), **meta_model[0].attributes)

        select_table = dict_model.select("surname == 'wdwdwd'")

        assert dict(expect) == dict(select_table)
        assert expect.attributes == select_table.attributes


class Test_union:

    def test_union_default_1(self, meta_model: QuadRowList):
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

    def test_union_default_2(self, meta_model: QuadRowList):
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

    def test_union_empty(self, meta_model: QuadRowList):
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

    def test_union_empty_reverse(self, meta_model: QuadRowList):
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

    def test_union_diff_attribs(self, meta_model: QuadRowList):
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
