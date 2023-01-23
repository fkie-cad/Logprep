# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=duplicate-code
# pylint: disable=function-redefined
import os
import time
import tempfile
from tests.unit.connector.base import BaseInputTestCase
from tests.testdata.input_logdata.file_input_logs import (
    test_initial_log_data,
    test_rotated_log_data,
    test_rotated_log_data_less_256,
)

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
        "start": "end",
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
            os.remove(self.object._config.logfile_path)

    def test_new_appended_logs_are_put_in_queue(self):
        wait_for_interval(CHECK_INTERVAL)
        queued_logs = []
        # empty queue with initial data
        before_append_offset = self.object._fileinfo_util.get_offset(
            self.object._config.logfile_path
        )
        append_file(self.object._config.logfile_path, test_rotated_log_data)
        wait_for_interval(CHECK_INTERVAL)
        while not self.object._messages.empty():
            queued_logs.append(self.object._messages.get(timeout=0.001))
        full_length = len(test_rotated_log_data)
        assert len(queued_logs) == full_length
        assert before_append_offset < self.object._fileinfo_util.get_offset(
            self.object._config.logfile_path
        )
