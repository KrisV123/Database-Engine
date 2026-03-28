import os
import mmap
from pathlib import Path
from database.tools.BaseModel import HighBaseModel
from database.tools.wal_comp import WAL

class Model(HighBaseModel):
    # key or superkey
    primary_key: list[str] = ['id']
    byte_model = 'I 20s 20s 20s f ?'
    path: Path = Path(__file__).parent

    def __init__(self, id: int,
                       krsne: str,
                       priezvysko: str | None,
                       dat_nar: str | None,
                       vyska: float | None,
                       ma_vodicak: bool | None):
        self.id = id
        self.krsne = krsne
        self.priezvysko = priezvysko
        self.dat_nar = dat_nar
        self.vyska = vyska
        self.ma_vodicak = ma_vodicak


if __name__ == '__main__':
    with WAL(Model, 'testing'):
        for i in range(50000):
            model = Model(i, 'Andrej', 'Meško', None, 152.5, True)
            model.send()

    import time
    start = time.time()
    table = Model.set()
    end = time.time()
    for key, column in table.items():
        print(key, column)
    #print(table)
    print(end - start)

    """with open(Model.path / 'data/tombstone.map', 'r+b') as f:
        #mm = mmap.mmap(f.fileno(), 0)
        #mm[0] = 239
        data = f.read()
        for byte in data:
            print(f'{byte:08b}')"""

    #Model.update("krsne == 'Kristian'", priezvysko = "'Veselý'")
    #print(Model.set())
    #Model.delete("krsne == 'Kristian'")
    #print(Model.set())

    """start = time.time()
    print(Model.set())
    end = time.time()
    print(end - start)"""

    Model.delete_table()

    """start = time.time()
    new_table = Model.set().select(
        "id <= 990 and vyska == 152.5 and ma_vodicak == true, krsne == 'Andrej' and priezvysko == 'Meško"
    )
    print(new_table)
    end = time.time()
    print(end - start)"""
