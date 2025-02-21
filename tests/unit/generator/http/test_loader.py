# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
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

    def test_init_sets_message_backlog_default(self):
        event_buffer = EventBuffer(self.file_loader)
        assert event_buffer._message_backlog.maxsize == DEFAULT_MESSAGE_BACKLOG_SIZE

    def test_init_sets_message_backlog_custom(self):
        random_size = random.randint(1, 100000)
        event_buffer = EventBuffer(self.file_loader, message_backlog_size=random_size)
        assert event_buffer._message_backlog.maxsize == random_size

    def test_write(self):
        self.file_loader.files = ["test_file.txt"]
        self.file_loader.event_count = 2

        event_buffer = EventBuffer(self.file_loader)
        mock_open = mock.mock_open(read_data="line1\nline2\n")

        old_size = event_buffer._message_backlog.qsize()
        with mock.patch("builtins.open", mock_open):
            event_buffer.write()
        assert event_buffer._message_backlog.qsize() == old_size + 3
        assert event_buffer._message_backlog.get() == "line1"
        assert event_buffer._message_backlog.get() == "line2"
        assert event_buffer._message_backlog.get() == event_buffer._sentinel

    def test_write_warns_if_queue_full(self, caplog):
        caplog.set_level(logging.WARNING)
        self.file_loader.files = ["test_file.txt"]
        self.file_loader.event_count = 2
        event_buffer = EventBuffer(self.file_loader, message_backlog_size=1)
        mock_open = mock.mock_open(read_data="line1\nline2\n")

        with (
            mock.patch("builtins.open", mock_open),
            mock.patch.object(event_buffer, "_message_backlog") as mock_queue,
        ):
            mock_queue.full = mock.MagicMock(return_value=True)
            event_buffer.write()

        assert "Message backlog queue is full" in caplog.text

    def test_read_yields_correct_events(self):
        self.file_loader.files = ["test_file.txt"]
        self.file_loader.event_count = 2

        event_buffer = EventBuffer(self.file_loader)
        mock_open = mock.mock_open(read_data="line1\nline2\n")

        with mock.patch("builtins.open", mock_open):
            event_buffer.write()
        reader = event_buffer.read_lines()
        assert next(reader) == "line1"
        assert next(reader) == "line2"

    def test_read_raises_stop_iteration(self):
        event_buffer = EventBuffer(self.file_loader)
        sentinel = event_buffer._sentinel
        event_buffer._message_backlog.put(sentinel)

        with pytest.raises(StopIteration):
            next(event_buffer.read_lines())

    def test_start_starts_thread(self):
        event_buffer = EventBuffer(self.file_loader)

        with mock.patch.object(Thread, "start") as mock_start:
            event_buffer.start()

        mock_start.assert_called_once()

    def test_stop_places_sentinel_in_queue(self):
        event_buffer = EventBuffer(self.file_loader)
        event_buffer._thread = mock.MagicMock()

        with mock.patch.object(event_buffer, "_message_backlog") as mock_queue:
            event_buffer.stop()
            mock_queue.put.assert_called_once_with(event_buffer._sentinel)

    def test_stop_stops_thread(self):
        event_buffer = EventBuffer(self.file_loader)
        event_buffer._thread = mock.MagicMock()
        event_buffer.stop()
        event_buffer._thread.join.assert_called_once()

    def test_start_thread(self):
        event_buffer = EventBuffer(self.file_loader)
        event_buffer._thread = mock.MagicMock()
        event_buffer._thread.is_alive.return_value = False
        event_buffer.start()
        event_buffer._thread.start.assert_called_once()

    def test_start_do_nothing_when_thread_is_alive(self):
        event_buffer = EventBuffer(self.file_loader)
        event_buffer._thread = mock.MagicMock()
        event_buffer._thread.is_alive.return_value = True
        event_buffer.start()
        assert event_buffer._thread.start.called is False


class TestFileLoader:
    """Test suite for the FileLoader class."""

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
        # assert loader._buffer.file_loader is loader

    # def test_overwrites_default(self):
    #     loader = FileLoader("", shuffle=True)
    #     assert loader.shuffle is True

    def test_initialization_non_existent_directory(self):
        with (
            mock.patch("pathlib.Path.exists", return_value=False),
            mock.patch("pathlib.Path.is_dir", return_value=False),
        ):
            loader = FileLoader("non_existent_dir")
            with pytest.raises(FileNotFoundError):
                loader.files

    def test_initialization_empty_directory(self):
        with mock.patch("pathlib.Path.glob", return_value=[]):
            loader = FileLoader("mocked_empty_dir")
            with pytest.raises(FileNotFoundError, match="No files found"):
                loader.files

    # def test_file_shuffling(self):
    #     with (mock.patch("random.shuffle") as mock_shuffle,):
    #         FileLoader("mocked_dir", shuffle=True)
    #         mock_shuffle.assert_called_once()

    def test_read_lines2(self):
        """Test that read_lines correctly delegates to the buffer's read_lines method."""
        mock_buffer = mock.MagicMock()
        mock_buffer.read_lines.return_value = iter(["Line1\n", "Line2\n"])
        mock_buffer.__enter__.return_value = mock_buffer
        mock_buffer.__exit__.return_value = None

        with mock.patch("logprep.generator.http.loader.EventBuffer", return_value=mock_buffer):
            loader = FileLoader("mock_dir")
            result = list(loader.read_lines())

        assert result == ["Line1\n", "Line2\n"]
        mock_buffer.read_lines.assert_called_once()

    ####

    # def test_infinite_read_lines(self):
    #     """Test if infinite_read_lines loops over files endlessly."""
    #     with (
    #         mock.patch(
    #             "builtins.open", new_callable=mock.mock_open, read_data="Line1\nLine2\n"
    #         ) as mock_file,
    #     ):
    #         loader = FileLoader("mock_dir")
    #         input_files = loader.files

    #         gen = loader.read_lines(input_files)
    #         output = [next(gen) for _ in range(6)]

    #         assert output == ["Line1\n", "Line2\n", "Line1\n", "Line2\n", "Line1\n", "Line2\n"]

    #         mock_file.assert_any_call("file1.txt", "r", encoding="utf8")
    #         mock_file.assert_any_call("file2.txt", "r", encoding="utf8")

    def test_clean_up(self):
        with (mock.patch("shutil.rmtree") as mock_rmtree,):
            loader = FileLoader("mock_dir")
            loader.clean_up()

            mock_rmtree.assert_called_once()


#     def test_without_mock(self, tmp_path):
#         lines = """first line
# second line
# third line
# """
#         first_file = tmp_path / "file1.txt"
#         second_file = tmp_path / "file2.txt"
#         first_file.write_text(lines)
#         second_file.write_text(lines)
#         self.file_loader = FileLoader(tmp_path)
#         lines = list(self.file_loader.read_lines())
#         assert lines
#         assert len(lines) == 6
#         assert lines[0] == "first line\n"
