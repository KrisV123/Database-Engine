from database.core.HighBaseModel import HighBaseModel
from pathlib import Path
from pprint import pprint
from dataclasses import dataclass
from typing import ClassVar, Annotated
import timeit

@dataclass(slots=True)
class Test(HighBaseModel):

    id: int
    name: Annotated[str, 20]
    surname: Annotated[str, 20]
    birth_date: Annotated[str, 10] | None = None
    email: Annotated[str, 40] | None = None
    phone_num: Annotated[str, 13] | None = None

    # key or superkey
    primary_key: ClassVar[tuple[str, ...]] = ('id',)

    # CREATED BY METACLASS
    # byte_model: ClassVar[str] = 'I 20s 20s 10s 40s 13s'
    # path: ClassVar[Path] = Path(__file__).parent
    # durability: ClassVar[bool] = True
    # integrity: ClassVar[bool] = False

"""
@WAL.decorator(Test, 'testing')
def tracked_transact(log_inst: WAL) -> Path:
    for i in range(20, 30):
        Test(i, 'Janko', 'Hrasko').send()
        #if i == 25:
        #    raise BaseException("Haha")
    return log_inst.log_file_path


@WAL.decorator(Test, 'testing')
def test_transact(_):
    Test.delete('True')
"""

def test():
    for i in range(1000):
        model = Test(
            i,
            'Kristian',
            'Vesely',
            '20.01.2001',
            'kris.v@gmail.com',
            None
        )
        model.send()
    Test.delete("name != 'Kristian'")
    Test.delete_table()

def test_2():
    for i in range(100_000):
        model = Test(
            i,
            'Kristian',
            'Vesely',
            '20.01.2001',
            'kris.v@gmail.com',
            None
        )
        model.send()

if __name__ == '__main__':
    print('IBA REGEX, lepsie re hladanie')
    times = []
    for i in range(10):
        time = timeit.timeit(test_2, number=1)
        times.append(time)
        print(time)
        Test.delete_table()
    priemer = sum(times) / len(times)
    print()
    print('PRIEMER:', priemer)
    #Test.delete_table()
    #pprint(Test.get_table_schema())
