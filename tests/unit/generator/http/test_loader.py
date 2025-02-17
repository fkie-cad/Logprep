# pylint: disable=missing-docstring
# pylint: disable=protected-access
import logging
import random
from pathlib import Path
from threading import Thread
from unittest import mock

import pytest

from logprep.generator.http.loader import EventBuffer, FileLoader
from logprep.util.defaults import DEFAULT_MESSAGE_BACKLOG_SIZE


class TestEventBuffer:

    def setup_method(self):
        self.file_loader = mock.MagicMock()

    def test_init(self):
        event_buffer = EventBuffer(self.file_loader)
        assert event_buffer
        assert event_buffer.file_loader == self.file_loader

    def test_init_sets_message_backlog_default(self):
        event_buffer = EventBuffer(self.file_loader)
        assert event_buffer._message_backlog.capacity == DEFAULT_MESSAGE_BACKLOG_SIZE

    def test_init_sets_message_backlog_custom(self):
        random_size = random.randint(1, 100000)
        event_buffer = EventBuffer(self.file_loader, message_backlog_size=random_size)
        assert event_buffer._message_backlog.capacity == random_size

    def test_write(self):
        self.file_loader.read_lines.return_value = ["line1", "line2"]
        event_buffer = EventBuffer(self.file_loader)
        old_size = event_buffer._message_backlog.qsize()
        event_buffer.write()
        assert event_buffer._message_backlog.qsize() == old_size + 2

    def test_write_warns_if_queue_full(self, caplog):
        caplog.set_level(logging.WARNING)
        self.file_loader.read_lines.return_value = ["line1", "line2"]
        event_buffer = EventBuffer(self.file_loader, message_backlog_size=1)
        with mock.patch.object(event_buffer, "_message_backlog") as mock_queue:
            mock_queue.full = mock.MagicMock(return_value=True)
            event_buffer.write()
        assert "Message backlog queue is full" in caplog.text

    def test_read_yields_correct_events(self):
        event_buffer = EventBuffer(self.file_loader)
        self.file_loader.read_lines.return_value = ["line1", "line2"]
        event_buffer.write()
        reader = event_buffer.read()
        assert next(reader) == "line1"
        assert next(reader) == "line2"

    def test_read_raises_stop_iteration(self):
        event_buffer = EventBuffer(self.file_loader)
        sentinel = event_buffer._sentinel
        self.file_loader.read_lines.return_value = [sentinel]
        event_buffer.write()
        reader = event_buffer.read()
        with pytest.raises(StopIteration):
            next(reader)

    def test_run_starts_and_joins_thread(self):
        event_buffer = EventBuffer(self.file_loader)

        with (
            mock.patch.object(Thread, "start") as mock_start,
            mock.patch.object(Thread, "join") as mock_join,
        ):
            event_buffer.run()

            mock_start.assert_called_once()
            mock_join.assert_called_once()

    def test_stop_places_sentinel_in_queue(self):
        event_buffer = EventBuffer(self.file_loader)

        with mock.patch.object(event_buffer, "_message_backlog") as mock_queue:
            event_buffer.stop()
            mock_queue.put.assert_called_once_with(event_buffer._sentinel)


def test_file_loader_initialization():
    """Test if FileLoader initializes correctly with mocked directory."""
    with (
        mock.patch("os.listdir", return_value=["file1.txt", "file2.txt"]),
        mock.patch("os.path.isdir", return_value=True),
        mock.patch("os.path.exists", return_value=True),
    ):

        loader = FileLoader("mocked_dir")

        assert loader.directory == Path("mocked_dir")
        assert loader.files == ["mocked_dir/file1.txt", "mocked_dir/file2.txt"]


def test_file_loader_default():
    loader = FileLoader("")
    assert loader.shuffle is False


def test_file_loader_overwrites_default():
    loader = FileLoader("", shuffle=True)
    assert loader.shuffle is True


def test_file_loader_initialization_non_existent_directory():
    with pytest.raises(FileNotFoundError):
        FileLoader("non_existent_dir")


def test_file_loader_initialization_empty_directory():
    with (
        mock.patch("os.listdir", return_value=[]),
        mock.patch("os.path.isdir", return_value=True),
        mock.patch("os.path.exists", return_value=True),
    ):
        with pytest.raises(ValueError, match="No files found"):
            FileLoader("mocked_empty_dir")


def test_file_loader_file_shuffling():
    with (
        mock.patch("os.listdir", return_value=["file1.txt", "file2.txt"]),
        mock.patch("os.path.isdir", return_value=True),
        mock.patch("os.path.exists", return_value=True),
        mock.patch("random.shuffle") as mock_shuffle,
    ):
        FileLoader("mocked_dir", shuffle=True)
        mock_shuffle.assert_called_once()


def test_file_loader_read_lines():
    with (
        mock.patch("os.listdir", return_value=["file1.txt", "file2.txt"]),
        mock.patch("os.path.isdir", return_value=True),
        mock.patch("os.path.exists", return_value=True),
        mock.patch(
            "builtins.open", new_callable=mock.mock_open, read_data="Line1\nLine2\n"
        ) as mock_file,
    ):
        loader = FileLoader("mock_dir")
        input_files = loader.files

        result = list(loader.read_lines(input_files))
        assert result == ["Line1\n", "Line2\n", "Line1\n", "Line2\n"]
        mock_file.assert_any_call("mock_dir/file1.txt", "r", encoding="utf8")
        mock_file.assert_any_call("mock_dir/file2.txt", "r", encoding="utf8")


def test_file_loader_infinite_read_lines():
    """Test if infinite_read_lines loops over files endlessly."""
    with (
        mock.patch("os.listdir", return_value=["file1.txt", "file2.txt"]),
        mock.patch("os.path.isdir", return_value=True),
        mock.patch("os.path.exists", return_value=True),
        mock.patch(
            "builtins.open", new_callable=mock.mock_open, read_data="Line1\nLine2\n"
        ) as mock_file,
    ):
        loader = FileLoader("mock_dir")
        input_files = loader.files

        gen = loader.infinite_read_lines(input_files)
        output = [next(gen) for _ in range(6)]

        assert output == ["Line1\n", "Line2\n", "Line1\n", "Line2\n", "Line1\n", "Line2\n"]

        mock_file.assert_any_call("mock_dir/file1.txt", "r", encoding="utf8")
        mock_file.assert_any_call("mock_dir/file2.txt", "r", encoding="utf8")


def test_file_loader_clean_up():
    with (
        mock.patch("os.listdir", return_value=["file1.txt", "file2.txt"]),
        mock.patch("os.path.isdir", return_value=True),
        mock.patch("os.path.exists", return_value=True),
        mock.patch("shutil.rmtree") as mock_rmtree,
    ):
        loader = FileLoader("mock_dir")
        loader.clean_up()

        mock_rmtree.assert_called_once()
