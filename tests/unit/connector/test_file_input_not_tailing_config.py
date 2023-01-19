# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
from copy import deepcopy
import json
import sys
import os
import time
import tempfile
import pytest
import requests
from logprep.connector.file.input import FileInput
from logprep.factory import Factory
from tests.unit.connector.base import BaseConnectorTestCase
from tests.testdata.input_logdata.file_input_logs import test_initial_log_data, test_rotated_log_data, test_rotated_log_data_less_256
import threading

new_file, testfile_location = tempfile.mkstemp()
check_interval = 0.1

def wait_for_interval(interval):
    time.sleep(2*interval)

def write_file(file_name: str, source_data: list):
    with open(file_name,"w") as file:
        for line in source_data:
            file.write(line + "\n")

def write_empty_file(file_name: str):
    open(file_name,"w").close()

def append_file(file_name: str, source_data: list):
    with open(file_name,"a") as file:
        for line in source_data:
            file.write(line + "\n")


class TestFileInput(BaseConnectorTestCase):
    def setup_class(self):
        if os.path.exists(testfile_location):
            os.remove(testfile_location)
        write_file(testfile_location, test_initial_log_data)

    def setup_method(self):
        super().setup_method()
        self.object.stopped = threading.Event()
        self.object.pipeline_index = 1
        self.object.setup()
        # we have to empty the queue for testing
        while not self.object._messages.empty():
            self.object._messages.get(timeout=0.001)

    def teardown_class(self):
        os.remove(testfile_location)

    def teardown_method(self):
        self.object.stopped.set()

    CONFIG: dict = {
        "type": "file_input",
        "documents_path": testfile_location,
        "start": "begin",
        "watch_file": False,
        "interval": check_interval
    }

    def test_create_connector(self):
        assert isinstance(self.object, FileInput)
   
    def test_has_thread_instance(self):
        assert isinstance(self.object.rt, threading.Thread)

    def test_thread_is_alive(self):
        assert self.object.rt.is_alive() == True

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

    def test_new_appended_logs_are_not_put_in_queue(self):
        wait_for_interval(check_interval)
        queued_logs = []
        before_append_offset = self.object._fileinfo_util.get_offset(self.object._config.documents_path)
        append_file(testfile_location, test_rotated_log_data)
        wait_for_interval(check_interval)
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        full_length = len(test_initial_log_data)
        assert len(queued_logs) == full_length
        assert before_append_offset == self.object._fileinfo_util.get_offset(self.object._config.documents_path)

    def test_not_reading_any_logs_after_rotating_filechange_detected(self):
        wait_for_interval(check_interval)
        queued_logs = []
        while not self.object._messages.empty():
            self.object._messages.get(timeout=0.001)
        before_change_offset = self.object._fileinfo_util.get_offset(self.object._config.documents_path)
        before_change_fingerprint = self.object._fileinfo_util.get_fingerprint(self.object._config.documents_path)
        write_file(testfile_location, test_rotated_log_data)
        wait_for_interval(check_interval)
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        assert len(queued_logs) == 0
        assert before_change_fingerprint == self.object._fileinfo_util.get_fingerprint(self.object._config.documents_path)
        assert before_change_offset == self.object._fileinfo_util.get_offset(self.object._config.documents_path)
