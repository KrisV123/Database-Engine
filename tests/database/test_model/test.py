from database.tools.BaseModel import HighBaseModel, Table, RowList
from database.tools.wal_comp import _LOG_INST, WAL
from pathlib import Path
from pprint import pprint
import time
import os
import timeit

class Test(HighBaseModel):
    # key or superkey
    primary_key: list[str] = ['id']
    byte_model = 'I 20s 20s 10s 40s 13s'
    path: Path = Path(__file__).parent

    def __init__(self,
                 id: int,
                 name: str,
                 surname: str,
                 birth_date: str | None = None,
                 email: str | None = None,
                 phone_num: str | None = None):
        self.id = id
        self.name = name
        self.surname = surname
        self.birth_date = birth_date
        self.email = email
        self.phone_num = phone_num

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


if __name__ == '__main__':
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
        """print('\n')
        print('LAST STATE:')
        print()
        for key, value in Test.set().items():
            print(key, value)
        print()"""

        Test.delete_table()
        import shutil
        shutil.rmtree(Test.path / 'data/wal_logs', ignore_errors=True)
    
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
