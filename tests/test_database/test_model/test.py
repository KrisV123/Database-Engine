#from database.tools.BaseModel import HighBaseModel, Table, RowList
from database.core.HighBaseModel import HighBaseModel
from database.core.meta import BaseModelMeta
from database.core.table_schema import TableSchema
from database.wal.wal import _LOG_INST, WAL
from pathlib import Path
from pprint import pprint
from dataclasses import dataclass
from typing import ClassVar, Annotated
import time
import os
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
    #byte_model: ClassVar[str] = 'I 20s 20s 10s 40s 13s'
    #path: ClassVar[Path] = Path(__file__).parent

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

if __name__ == '__main__':
    #schema = TableSchema.init_meta(Test)
    pprint(TableSchema.check_table_schema(Test, Test.path))
    """
    try:
        with WAL(Test, 'testing') as log_inst:
            for i in range(20, 30):
                Test(i, 'Janko', 'Hrasko').send()
            log_path = log_inst.log_file_path
        
        with open(log_path, 'r+b') as log_f:
            log_f.seek(120)
            log_f.write(b'f' * 300)

        for log in WAL.iter_logs(Test, log_path, True):
            pprint(log)
            print()


        #print()
        #pprint(WAL.get_header(Test.path / 'data/wal_logs/testing'))
        #WAL.print_logs(Test, Test.path / 'data/wal_logs/testing', True)
    finally:
        pass
        #print('\n')
        #print('LAST STATE:')
        #print()
        #for key, value in Test.set().items():
        #    print(key, value)
        #print()

        Test.delete_table()
        import shutil
        shutil.rmtree(Test.path / 'data/wal_logs', ignore_errors=True)
    """

    """WAL.rollback(Test, Test.path / 'data/wal_logs/testing')
    print()

    for key, col in Test.set().items():
        print(key, col)"""

    """print()
    WAL.print_logs(Test, 'database/test_model/data/wal_logs/testing', format=True)
    print()

    header = WAL.get_header('database/test_model/data/wal_logs/testing')
    print(header.STATUS)

    Test.delete_table()
    import shutil
    shutil.rmtree(Test.path / 'data/wal_logs', ignore_errors=True)"""

    """
    from typing import Any, Annotated, get_type_hints

    class ModelMeta(type):
        def __new__(cls, name: str, bases: tuple[type,...], namespaces: dict[str, Any]):
            ann: dict | None = namespaces.get('__annotations__')
            assert ann is not None

            new_cls = super().__new__(cls, name, bases, namespaces)

            raw_annotations = namespaces.get('__annotations__')
            if raw_annotations:
                resolved = get_type_hints(new_cls, include_extras=True)
                own_annotations = {k: resolved[k] for k in raw_annotations if k in resolved}
                pprint(own_annotations)

            return new_cls

    @dataclass(slots=True)
    class Model(HighBaseModel):
        id: int
        name: Annotated[str, 20]
        surname: Annotated[str, 20] | None
    """
