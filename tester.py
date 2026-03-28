from database.tools.literal_parser import *
from typing import Any
from database.tools.BaseModel import Table, RowList
from database.test_model.test import Test
from dataclasses import dataclass, field
import timeit

attribs_1 = {'id': 0, 'name': 1}

column_1_1 = RowList([1, 'Kristian'], **attribs_1)
column_2_1 = RowList([2, 'Andrej'], **attribs_1)
column_3_1 = RowList([4, 'Adam'], **attribs_1)
column_4_1 = RowList([10, 'Jozko'], **attribs_1)

table_1 = Table({
            (column_1_1[0],): column_1_1,
            (column_2_1[0],): column_2_1,
            (column_3_1[0],): column_3_1,
            (column_4_1[0],): column_4_1,
            },
            **attribs_1
        )
column_1_1_copy = column_1_1.copy()
assert column_1_1 == column_1_1_copy

attribs_2 = {'id': 0, 'sallery': 1}

column_1_2 = RowList([1, 5000], **attribs_2)
column_2_2 = RowList([1, 8000], **attribs_2)
column_3_2 = RowList([4, 20000], **attribs_2)
column_4_2 = RowList([5, 15000], **attribs_2)

table_2 = Table({
            tuple(column_1_2): column_1_2,
            tuple(column_2_2): column_2_2,
            tuple(column_3_2): column_3_2,
            tuple(column_4_2): column_4_2
            },
            **attribs_2
        )

#join_table = table_1.join('INNER', table_2, 'id')

row = table_2[(1, 5000)]

"""print(column_1_1.attributes)
del_attr = column_1_1.pop_named('Surname')
print()
print(column_1_1.attributes)"""


"""attribs = {'id': 0, 'Name': 1, 'Surname': 2}

column_1_1 = RowList([1, 'Andrej', 'Meško'], **attribs)
column_1_2 = RowList([2, 'Kristian', 'Vesely'], **attribs)
column_1_3 = RowList([3, 'Adam', 'Kocan'], **attribs)
column_1_4 = RowList([4, 'Jozko', 'Mrkvicka'], **attribs)

table_1 = Table({
    (column_1_1[0],): column_1_1,
    (column_1_2[0],): column_1_2,
    (column_1_3[0],): column_1_3,
    (column_1_4[0],): column_1_4
    },
    **attribs
)

table_2 = Table({
    (column_1_1[0],): column_1_1,
    (column_1_2[0],): column_1_2
    },
    **attribs
)

diff_table = table_1.difference(table_2)
diff_table = table_1.union(table_2)"""

"""attribs_1 = {'Name': 0, 'Surname': 1, 'Country': 2}

column_2_1 = RowList(['Andrej', 'Meško', 'Switzerland'], **attribs_1)
column_2_2 = RowList(['Kristian', 'Vesely', 'Czechia'], **attribs_1)
column_2_3 = RowList(['Adam', 'Kocan', 'Slovakia'], **attribs_1)

table_2 = Table({
    (column_2_1[0], column_2_1[1]): column_2_1,
    (column_2_2[0], column_2_2[1]): column_2_2,
    (column_2_3[0], column_2_3[1]): column_2_3,
    },
    **attribs_1
)"""

#int_byte = int.from_bytes(my_byte, byteorder='little', signed=False)

column = RowList(['Kristian', 'Vesely'], name=0, surname=1)
vals = ['Kristian', 'Vesely']
copy_column = RowList(vals, Name_2=1, Surname_2=1)


"""num = (9 << 999)

def _test():
    varint = WAL.VarInt.to_varint(num)

import timeit

print(timeit.timeit(_test, number=10000))"""

"""enum = enumerate(['a', 'b', 'c'])
for x, y in enum:
    print(x, y)"""

"""for byte in varint:
    print(bin(byte))
    #print(int(byte))

print(WAL.VarInt.to_int(varint))"""

"""import timeit

def _test():
    WAL.VarInt.to_int(b'\x98\xe9\x99\x0c\x98\xe9\x99\x0c')

print(timeit.timeit(_test, number=1000000))"""

"""my_bytes = b'\x76\x76\x76\x77\x77'

print(WAL.VarInt.to_int(my_bytes))

for byte in my_bytes:
    print(bin(byte))


from collections.abc import Generator, Iterable

class MyGenerator(Generator):
    def __init__(self, gener: Iterable):
        super().__init__()"""

import timeit

"""for i in range(5000):
    model = Test(
        i,
        'Adam',
        'Kocan'
    )
    model.send()

Test.delete("id == 4857")"""

def test():
    Test.find_empty_space()

"""try:
    print('NEW')
    print(timeit.repeat(test, repeat=30, number=50000))
    print('END')
finally:
    pass
    #Test.delete_table()"""

"""
### TESTING MODEL

for key, col in Test.set().items():
    print(key, col)

print()
WAL.commit(Test, 'database/test_model/data/wal_logs/testing')

for key, col in Test.set().items():
    print(key, col)
"""


# IM COOKIN SOMETHING !!!!!!!!!!!!!!!!!!!!

from collections.abc import Callable

fun: dict[str, Callable] = {
    'add': lambda x, y: x + y,
    'multi': lambda x, y: x * y,
    'ident': lambda x: x
}

# (1 + 2) * (3 + 4)

"""
            *
        /       \\    
    +               +
  /   \\         /     \
1       2       3       4
"""

vars: dict[str, int] = {
    'x': 1,
    'y': 2,
    'z': 3,
    'w': 4
}

ans = fun['multi'](
        fun['add'](
            fun['ident'](
                vars['x']
            ),
            fun['ident'](
                vars['y']
            )
        ),
        fun['add'](
            fun['ident'](
                vars['z']
            ),
            fun['ident'](
                vars['w']
            )
        )
)

#print(ans)

"""
2 * (2 + 3)

            *
        /       \\
        2       +
            /       \\
            2       3
"""


"""
2 * 2 + 3

            +
        /       \\
        *       3
    /       \\
    2       2
"""


from typing import get_args, get_origin

class MyClass[T]:
    pass

inst = MyClass[int]()
alias = inst.__orig_class__ #type:ignore
#print(get_args(alias))


column_1 = RowList([1, 'Kristian'], id=0, name=1)
column_2 = RowList(['Vesely', 'Czechia', None], surname=0, country=1, neviem=2)

new = column_1 + column_2
val = new[2]

column_3 = RowList([1, 'Andrej'], id=0, name=1)
column_4 = RowList([False, False, False], surname=0, country=1, neviem=2)


from typing import get_type_hints

"""for var in sign.parameters.values():
    print(var.annotation)
    print(type(var.annotation))
    print()"""


test_attribs = {
    'id': 0, 'name': 1, 'surname': 2,
    'birth_date': 3, 'email': 4, 'phone_num': 5
}
test_column = RowList[int | str | None](
    [1, 'Kristian', 'Vesely', None, None, None],
    **test_attribs
)

test_inst = Test.from_row(test_column)
#print(test_inst)

#print(get_type_hints(Test.__init__))


#print(True and 5 in [4,5,6])
print(2 != 3)