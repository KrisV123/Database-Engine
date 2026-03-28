"""
Scrip form making model templates. Model will be directly created
inside database folder. Model can be also created without script,
but there need to satisfy structure

STRUCTURE:

    "model dir"/
        "data dir"/
            data.bin
            tombstone.map
        "python model file"

In python file needs to be everything as in template_txt
"""

from pathlib import Path
from textwrap import dedent
import re

class ModelConstructor():
    root_path = Path(__file__).parents[1]

    def __init__(self, name: str):
        new_path = Path(self.root_path / 'database' / f'{name}_model')

        new_path.mkdir(exist_ok=False)
        Path(new_path / 'data').mkdir(exist_ok=False)
        Path(new_path / 'data' / 'data.bin').touch()
        Path(new_path / 'data' / 'tombstone.map').touch()
        Path(new_path / f'{name}.py').touch()

        template_txt = dedent(f"""\
            from tools.BaseModel import HighBaseModel
            from pathlib import Path 
            
            class {name[0].upper() + name[1:]}:
                # key or superkey
                primary_key: list[str] = []
                byte_model = ''
                path: Path = Path(__file__).parent

                def __init__(self):
                    pass
        """)

        with open(self.root_path / 'database' / f'{name}_model' / f'{name}.py', 'w') as f:
            f.write(template_txt)


if __name__ == '__main__':

    print('Ready to create tables...')

    while True:
        new_input = input()

        if new_input == 'exit()':
            break

        pattern = r'ModelConstructor\((["\'])([a-zA-Z_]+)\1\)'
        match = re.match(pattern, new_input)
        if match:
            print(match)
            try:
                ModelConstructor(match.group(2))
                print('model created')
            except:
                print('ERROR: not valid syntax or wrong params')
        else:
            print('ERROR: no match')