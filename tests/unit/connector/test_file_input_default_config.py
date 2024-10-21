# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=duplicate-code
# pylint: disable=function-redefined
# pylint: disable=unnecessary-dunder-call
# pylint: disable=broad-except
import os
import tempfile
import threading
import time

import pytest

from logprep.abc.input import FatalInputError
from logprep.connector.file.input import FileInput
from tests.testdata.input_logdata.file_input_logs import (
    test_initial_log_data,
    test_rotated_log_data,
    test_rotated_log_data_less_256,
)
from tests.unit.connector.base import BaseInputTestCase

CHECK_INTERVAL = 0.1


def wait_for_interval(interval):
    time.sleep(2 * interval)


def write_file(file_name: str, source_data: list):
    with open(file_name, "w", encoding="utf-8") as file:
        for line in source_data:
            file.write(line + "\n")


def write_empty_file(file_name: str):
    open(file_name, "w", encoding="utf-8").close()


def append_file(file_name: str, source_data: list):
    with open(file_name, "a", encoding="utf-8") as file:
        for line in source_data:
            file.write(line + "\n")


class TestFileInput(BaseInputTestCase):
    CONFIG: dict = {
        "type": "file_input",
        "logfile_path": "",
        "start": "begin",
        "watch_file": True,
        "interval": CHECK_INTERVAL,
    }

    def setup_method(self):
        _, testfile = tempfile.mkstemp()
        write_file(testfile, test_initial_log_data)
        self.CONFIG["logfile_path"] = testfile
        super().setup_method()
        self.object.pipeline_index = 1
        self.object.setup()
        # we have to empty the queue for testing
        while not self.object._messages.empty():
            self.object._messages.get(timeout=0.001)

    def teardown_method(self):
        self.object.stop_flag.set()
        if not self.object.rthread.is_alive():
            try:
                os.remove(self.object._config.logfile_path)
            except Exception:
                pass

    def test_create_connector(self):
        assert isinstance(self.object, FileInput)

    def test_has_thread_instance(self):
        assert isinstance(self.object.rthread, threading.Thread)

    def test_thread_is_alive(self):
        assert self.object.rthread.is_alive() is True

    def test_offset_is_set_and_not_null(self):
        assert self.object._fileinfo_util.get_offset(self.object._config.logfile_path) != 0

    def test_offset_is_set_and_not_null(self):
        assert self.object._fileinfo_util.get_fingerprint(self.object._config.logfile_path) != 0

    def test_init_filewatcher_util_dict_with_emtpy_dict(self):
        wait_for_interval(CHECK_INTERVAL)
        test_string = "test_file"
        self.object._fileinfo_util.__init__("test_file")
        assert test_string in self.object._fileinfo_util.dict.keys()

    def test_filewatcher_util_updates_fingerprint_size(self):
        wait_for_interval(CHECK_INTERVAL)
        test_value = 1000
        test_path = "test_path"
        self.object._fileinfo_util.add_fingerprint_size(test_path, test_value)
        assert self.object._fileinfo_util.get_fingerprint_size(test_path) == test_value

    def test_filewatcher_util_returns_empty_string_on_nonexistent_file_name(self):
        assert self.object._fileinfo_util.get_fingerprint_size("another_test_path") == ""

    def test_filewatcher_util_returns_empty_string_on_not_set_fingerprint_size(self):
        self.object._fileinfo_util.add_file("another_test_path")
        assert self.object._fileinfo_util.get_fingerprint_size("another_test_path") == ""

    def test_filewatcher_util_returns_false_when_checked_fingerprint_doesnt_exist(self):
        assert self.object._fileinfo_util.has_fingerprint_changed("another_test_path", 0) is False

    def test_exit_on_shutdown(self):
        self.object.shut_down()
        wait_for_interval(CHECK_INTERVAL)
        assert self.object.rthread.is_alive() is False

    def test_pipeline_index_not_there(self):
        delattr(self.object, "pipeline_index")
        with pytest.raises(FatalInputError):
            self.object.setup()

    @pytest.mark.filterwarnings("ignore:Exception in thread")
    def test_raise_error_file_gets_removed(self):
        wait_for_interval(CHECK_INTERVAL)
        os.remove(self.object._config.logfile_path)
        wait_for_interval(CHECK_INTERVAL)
        assert self.object.rthread.is_alive() is False
        assert isinstance(self.object.rthread.exception, FatalInputError)

    @pytest.mark.filterwarnings("ignore:Exception in thread")
    def test_raise_error_file_gets_unreadable_permissions(self):
        wait_for_interval(CHECK_INTERVAL)
        os.chmod(self.object._config.logfile_path, 0o111)
        wait_for_interval(CHECK_INTERVAL)
        assert self.object.rthread.is_alive() is False
        assert isinstance(self.object.rthread.exception, FatalInputError)

    def test_get_event_with_empty_queue_returns_none(self):
        wait_for_interval(CHECK_INTERVAL)
        while not self.object._messages.empty():
            self.object._messages.get(timeout=0.001)
        assert self.object._get_event(timeout=0.001) == (None, None)

    def test_input_line_function_returns_empty_string(self):
        wait_for_interval(CHECK_INTERVAL)
        assert self.object._line_to_dict("") == ""

    def test_log_from_file_with_get_next(self):
        wait_for_interval(CHECK_INTERVAL)
        get_next_log_line = self.object.get_next(timeout=0.001)
        assert get_next_log_line.get("message") == test_initial_log_data[0]

    def test_log_from_file_is_put_in_queue(self):
        wait_for_interval(CHECK_INTERVAL)
        log_line_from_queue = self.object._messages.get(timeout=0.001)
        assert log_line_from_queue.get("message") == test_initial_log_data[0]

    def test_all_logs_form_file_are_put_in_queue(self):
        wait_for_interval(CHECK_INTERVAL)
        queued_logs = []
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        assert len(queued_logs) == len(test_initial_log_data)

    def test_new_appended_logs_are_put_in_queue(self):
        wait_for_interval(CHECK_INTERVAL)
        queued_logs = []
        before_append_offset = self.object._fileinfo_util.get_offset(
            self.object._config.logfile_path
        )
        append_file(self.object._config.logfile_path, test_rotated_log_data)
        wait_for_interval(CHECK_INTERVAL)
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        full_length = len(test_initial_log_data) + len(test_rotated_log_data)
        assert len(queued_logs) == full_length
        # file offset has to be bigger after apending as
        # it should've continued
        assert before_append_offset < self.object._fileinfo_util.get_offset(
            self.object._config.logfile_path
        ), "file offset becomes bigger after new loglines got appended"

    def test_read_all_logs_after_rotating_filechange_detected(self):
        wait_for_interval(CHECK_INTERVAL)
        queued_logs = []
        while not self.object._messages.empty():
            self.object._messages.get(timeout=0.001)
        before_change_offset = self.object._fileinfo_util.get_offset(
            self.object._config.logfile_path
        )
        before_change_fingerprint = self.object._fileinfo_util.get_fingerprint(
            self.object._config.logfile_path
        )
        write_file(self.object._config.logfile_path, test_rotated_log_data)
        wait_for_interval(CHECK_INTERVAL)
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        assert len(queued_logs) == len(test_rotated_log_data)
        assert before_change_fingerprint != self.object._fileinfo_util.get_fingerprint(
            self.object._config.logfile_path
        )
        assert before_change_offset > self.object._fileinfo_util.get_offset(
            self.object._config.logfile_path
        ), "After Filechange to smaller file the file offset is smaller afterwards"

    @pytest.mark.skipif(os.environ.get("GITHUB_ACTIONS") == "true", reason="sometimes fails on CI")
    def test_get_unique_logs_after_rotating_filechange_detected_with_filesize_smaller_256(self):
        """it can occur that a logfile is smaller than 256 bytes after rotation,
        in this case every appending file change would act like the detection of a log rotated file
        while it stays smaller than 256 bytes, which could lead to duplicate processed log lines
        therefore the size of the fingerprint needs to be flexible after log rotation"""
        wait_for_interval(CHECK_INTERVAL)
        queued_logs = []
        while not self.object._messages.empty():
            self.object._messages.get(timeout=0.001)
        write_empty_file(self.object._config.logfile_path)
        wait_for_interval(CHECK_INTERVAL)
        empty_file_fingerprint_size = self.object._fileinfo_util.get_fingerprint_size(
            self.object._config.logfile_path
        )
        append_file(self.object._config.logfile_path, test_rotated_log_data_less_256)
        wait_for_interval(2 * CHECK_INTERVAL)
        first_small_file_fingerprint_size = self.object._fileinfo_util.get_fingerprint_size(
            self.object._config.logfile_path
        )
        append_file(self.object._config.logfile_path, test_rotated_log_data_less_256)
        wait_for_interval(CHECK_INTERVAL)
        second_small_file_fingerprint_size = self.object._fileinfo_util.get_fingerprint_size(
            self.object._config.logfile_path
        )
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        assert first_small_file_fingerprint_size == second_small_file_fingerprint_size
        assert empty_file_fingerprint_size == 256
        assert len(queued_logs) == 2
