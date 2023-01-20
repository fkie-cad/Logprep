# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=duplicate-code
# pylint: disable=function-redefined
import os
import threading
import time
import tempfile
import pytest
from logprep.connector.file.input import FileInput
from tests.unit.connector.base import BaseInputTestCase
from tests.testdata.input_logdata.file_input_logs import (
    test_initial_log_data,
    test_rotated_log_data,
    test_rotated_log_data_less_256,
)

check_interval = 0.1


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
        "documents_path": "",
        "start": "begin",
        "watch_file": True,
        "interval": check_interval,
    }

    def setup_method(self):
        _, testfile = tempfile.mkstemp()
        write_file(testfile, test_initial_log_data)
        self.CONFIG["documents_path"] = testfile
        super().setup_method()
        self.object.pipeline_index = 1
        self.object.setup()
        # we have to empty the queue for testing
        while not self.object._messages.empty():
            self.object._messages.get(timeout=0.001)

    def teardown_method(self):
        self.object.stop_flag.set()
        if not self.object.rthread.is_alive():
            os.remove(self.object._config.documents_path)

    def test_create_connector(self):
        assert isinstance(self.object, FileInput)

    def test_has_thread_instance(self):
        assert isinstance(self.object.rthread, threading.Thread)

    def test_thread_is_alive(self):
        assert self.object.rthread.is_alive() is True

    def test_offset_is_set_and_not_null(self):
        assert self.object._fileinfo_util.get_offset(self.object._config.documents_path) != 0

    def test_offset_is_set_and_not_null(self):
        assert self.object._fileinfo_util.get_fingerprint(self.object._config.documents_path) != 0

    def test_log_from_file_is_put_in_queue(self):
        wait_for_interval(check_interval)
        log_line_from_queue = self.object._messages.get(timeout=0.001)
        assert log_line_from_queue.get("message") == test_initial_log_data[0]

    def test_all_logs_form_file_are_put_in_queue(self):
        wait_for_interval(check_interval)
        queued_logs = []
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        assert len(queued_logs) == len(test_initial_log_data)

    def test_new_appended_logs_are_put_in_queue(self):
        wait_for_interval(check_interval)
        queued_logs = []
        before_append_offset = self.object._fileinfo_util.get_offset(
            self.object._config.documents_path
        )
        append_file(self.object._config.documents_path, test_rotated_log_data)
        wait_for_interval(check_interval)
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        full_length = len(test_initial_log_data) + len(test_rotated_log_data)
        assert len(queued_logs) == full_length
        # file offset has to be bigger after apending as
        # it should've continued
        assert before_append_offset < self.object._fileinfo_util.get_offset(
            self.object._config.documents_path
        )

    def test_read_all_logs_after_rotating_filechange_detected(self):
        wait_for_interval(check_interval)
        queued_logs = []
        while not self.object._messages.empty():
            self.object._messages.get(timeout=0.001)
        before_change_offset = self.object._fileinfo_util.get_offset(
            self.object._config.documents_path
        )
        before_change_fingerprint = self.object._fileinfo_util.get_fingerprint(
            self.object._config.documents_path
        )
        write_file(self.object._config.documents_path, test_rotated_log_data)
        wait_for_interval(check_interval)
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        assert len(queued_logs) == len(test_rotated_log_data)
        assert before_change_fingerprint != self.object._fileinfo_util.get_fingerprint(
            self.object._config.documents_path
        )
        # file offset has to be smaller after writing as
        # it should've started again on a second smaller file
        assert before_change_offset > self.object._fileinfo_util.get_offset(
            self.object._config.documents_path
        )

    def test_get_unique_logs_after_rotating_filechange_detected_with_filesize_smaller_256(self):
        """it can occur that a logfile is smaller than 256 bytes after rotation,
        in this case every appending file change would act like the detection of a log rotated file
        while it stays smaller than 256 bytes, which could lead to duplicate processed log lines
        therefore the size of the fingerprint needs to be flexible after log rotation"""
        wait_for_interval(check_interval)
        queued_logs = []
        while not self.object._messages.empty():
            self.object._messages.get(timeout=0.001)
        write_empty_file(self.object._config.documents_path)
        wait_for_interval(check_interval)
        empty_file_fingerprint_size = self.object._fileinfo_util.get_fingerprint_size(
            self.object._config.documents_path
        )
        # append first line to empty file with less than 256 byte in total
        append_file(self.object._config.documents_path, test_rotated_log_data_less_256)
        wait_for_interval(2*check_interval)
        first_small_file_fingerprint_size = self.object._fileinfo_util.get_fingerprint_size(
            self.object._config.documents_path
        )
        # append second line to empty file with less than 256 byte in total
        append_file(self.object._config.documents_path, test_rotated_log_data_less_256)
        wait_for_interval(check_interval)
        second_small_file_fingerprint_size = self.object._fileinfo_util.get_fingerprint_size(
            self.object._config.documents_path
        )
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        assert first_small_file_fingerprint_size == second_small_file_fingerprint_size
        assert empty_file_fingerprint_size == 256
        assert len(queued_logs) == 2
