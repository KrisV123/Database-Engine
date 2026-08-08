from __future__ import annotations
import pytest #type:ignore[import-not-found]

from database.tools.core.row import RowList

@pytest.fixture
def line_1() -> RowList[int | str]:
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
