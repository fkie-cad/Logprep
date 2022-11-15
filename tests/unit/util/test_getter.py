import pytest
from logprep.util.getter import FileGetter, GetterFactory


class TestFileGetter:
    def test_factory_returns_file_getter(self):
        file_getter = GetterFactory.from_string("/my/file")
        assert isinstance(file_getter, FileGetter)
