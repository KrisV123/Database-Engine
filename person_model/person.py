from pathlib import Path
from dataclasses import dataclass
from typing import ClassVar, Annotated
from pprint import pprint

from database.core.HighBaseModel import HighBaseModel
from database.wal.wal import WAL

@dataclass(slots=True)
class Model(HighBaseModel):

    id: Annotated[int, "unsigned int"]
    krsne: Annotated[str, 20]
    priezvysko: Annotated[str, 20] | None
    dat_nar: Annotated[str, 20] | None
    vyska: Annotated[float, "float"] | None
    ma_vodicak: bool | None

    # primary key
    primary_key: ClassVar[tuple[str, ...]] = ('id',)


def setup_table() -> None:
    for i in range(10):
        model = Model(
            i, 'Kristian', None, '20.01.2001',
            187.5, True
        )
        model.send()
    pprint(Model.set())

def tracked_delete() -> int:
    with WAL(Model, 'testing'):
        count = Model.delete('id < 20')
    pprint(Model.set())
    return count

def untracked_delete() -> int:
    count = Model.delete('id < 20')
    pprint(Model.set())
    return count

def delete_table() -> None:
    Model.delete_table()
    pprint(Model.set())

def rollback_log(file: Path):
    WAL.rollback(Model, file)
    pprint(Model.set())

def combined_tracked_transaction() -> None:
    with WAL(Model, 'testing'):
        new_line = Model(110, 'Andrej', 'Mesko', '18.02.2001', 162.3, True)
        new_line.send()

        Model.delete('2 < id < 8')
        Model.update('id < 100', krsne="'Adam'")

        Model.delete_table()

        Model(5, 'Jozko', 'Mrkvicka', '69.7.2000', 110.2, False).send()

def untracked_update() -> None:
    Model.update('id < 100', krsne="'Adam'")
    pprint(Model.set())

def tracked_delete_table() -> None:
    with WAL(Model, 'testing'):
        Model.delete_table()
    pprint(Model.set())

if __name__ == '__main__':

    #table_schema = Model.get_table_schema()
    #pprint(table_schema)

    #print(Model.get_byte_model_list())
    #print(Model.get_endianness_symbol())

    """
    Model.delete_table()

    model = Model(
        1, 'Kristian', 'Vesely', '20.01.2001',
        187.5, True
    )
    model.send()
    pprint(Model.set())

    Model.delete_table()
    """

    Model.delete_table()
    Model.delete_table()
    setup_table()
    combined_tracked_transaction()
    pprint(Model.set())
    Model.delete_table()

    #WAL.rollback(Model, Path('person_model/data/wal_logs/testing_26-08-26_22-44-359215.log'))
    #pprint(Model.set())

    """
    Model.delete_table()
    setup_table()
    pprint(Model.set())
    print()
    combined_tracked_transaction()
    pprint(Model.set())
    print()
    """

    """
    Model.delete_table()

    setup_table()
    Model.delete("id == 8")

    Model(8, '', '', '', 187.1, True, 69).send()

    print()
    pprint(Model.set())

    Model.delete_table()
    """

    #setup_table()
    #combined_tracked_transaction()
    #pprint(Model.set())

    #WAL.rollback(Model, 'database/person_model/data/wal_logs/testing_26-07-26_15-09-870166.log')
    #pprint(Model.set())

    #Model.delete_table()

    """
    rollback_log('database/person_model/data/wal_logs/testing_26-07-23_23-29-576770.log')
    pprint(Model.set())
    """
    #delete_table()
    #combined_tracked_transaction()
    #delete_table()

    """
    with WAL(Model, 'testing'):
        for i in range(10, 15):
            model = Model(i, 'Andrej', 'Meško', None, 152.5, True)
            model.send()

    pprint(Model.set())
    """

    """
    with WAL(Model, 'testing'):
        Model.delete('1 < id < 100')
    print(Model.set())
    """

    #WAL.rollback(Model, Path('database/person_model/data/wal_logs/testing_26-07-22_19-13-168880.log'))
    #pprint(Model.set())

    #Model.delete_table()

    """start = time.time()
    new_table = Model.set().select(
        "id <= 990 and vyska == 152.5 and ma_vodicak == true, krsne == 'Andrej' and priezvysko == 'Meško"
    )
    print(new_table)
    end = time.time()
    print(end - start)"""

    """
    person = Model(1, 'Kristian', 'Vesely', '20.1', 187.0, True)
    person.send()
    
    table = Model.set()
    pprint(table)
    """

    """
    Model.delete_table()
    setup_table()
    pprint(Model.set())
    print()
    print(Model.byte_model)
    Model.delete_table()
    """
