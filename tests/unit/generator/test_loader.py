# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from pathlib import Path
from unittest import mock

import pytest

from logprep.generator.loader import FileLoader


class TestFileLoader:

    def setup_method(self):
        self.mock_listdir = mock.patch("pathlib.Path.glob", return_value=["file1.txt", "file2.txt"])
        self.mock_isdir = mock.patch("pathlib.Path.is_dir", return_value=True)
        self.mock_exists = mock.patch("pathlib.Path.exists", return_value=True)

        self.mock_listdir.start()
        self.mock_isdir.start()
        self.mock_exists.start()

    def teardown_method(self):
        mock.patch.stopall()

    def test_init(self):
        loader = FileLoader("mocked_dir")
        assert loader.directory == Path("mocked_dir")
        assert loader.files == ["file1.txt", "file2.txt"]

    def test_initialization_non_existent_directory(self):
        with (
            mock.patch("pathlib.Path.exists", return_value=False),
            mock.patch("pathlib.Path.is_dir", return_value=False),
        ):
            loader = FileLoader("non_existent_dir")
            with pytest.raises(FileNotFoundError) as error:
                assert loader.files == error

    def test_initialization_empty_directory(self):
        with mock.patch("pathlib.Path.glob", return_value=[]):
            loader = FileLoader("mocked_empty_dir")
            with pytest.raises(FileNotFoundError, match="No files found") as error:
                assert loader.files == error

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="line1\nline2\n")
    def test_read_lines(self, mock_file):
        loader = FileLoader("mock_dir")
        result = list(loader.read_lines())

        assert result == ["line1\n", "line2\n", "line1\n", "line2\n"]
        assert mock_file.call_count == 2

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="line1\nline2\n")
    def test_read_lines_with_exit_requested(self, mock_file):
        loader = FileLoader("mock_dir")
        loader.exit_requested = True
        result = list(loader.read_lines())

        assert result == ["line1\n"]
        assert mock_file.call_count == 1

    def test_clean_up(self):
        with (mock.patch("shutil.rmtree") as mock_rmtree,):
            loader = FileLoader("mock_dir")
            loader.clean_up()

            mock_rmtree.assert_called_once()
