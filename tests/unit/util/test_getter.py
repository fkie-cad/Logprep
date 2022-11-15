# pylint: disable=missing-docstring
from unittest import mock
from logprep.util.getter import FileGetter, GetterFactory


class TestFileGetter:
    def test_factory_returns_file_getter(self):
        file_getter = GetterFactory.from_string("/my/file")
        assert isinstance(file_getter, FileGetter)

    def test_get_returns_content(self):
        file_getter = GetterFactory.from_string("/my/file")
        with mock.patch("io.open", mock.mock_open(read_data="my content")):
            content = file_getter.get()
            assert content == "my content"
