from json import dumps
from os import unlink
from tempfile import NamedTemporaryFile


class FilledTempFile:
    def __init__(self, content):
        self._content = content
        self._temp_file = None
        self._temp_path = None

    def __enter__(self):
        self._temp_file = NamedTemporaryFile(delete=False)
        self._temp_file.write(self._content)
        self._temp_file.close()

        return self._temp_file.name

    def __exit__(self, exc_type, exc_val, exc_tb):
        unlink(self._temp_file.name)


class JsonTempFile(FilledTempFile):
    def __init__(self, rule):
        super().__init__(bytes(dumps(rule), encoding="utf-8"))
