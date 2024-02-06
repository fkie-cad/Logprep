# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import os
import shutil
from unittest import mock

import responses

from logprep.event_generator.http.controller import Controller
from tests.unit.event_generator.http.util import create_test_event_files


class TestController:
    def setup_method(self):
        self.target_url = "http://testendpoint"
        self.batch_size = 10
        self.contoller = Controller(
            input_dir="",
            batch_size=self.batch_size,
            replace_timestamp=True,
            tag="testdata",
            report=True,
            target_url=self.target_url,
            user="test-user",
            password="pass",
            thread_count=1,
        )

    def teardown_method(self):
        experiment_dir = self.contoller.reporter.experiment_dir
        if os.path.isdir(experiment_dir):
            shutil.rmtree(experiment_dir)

    @responses.activate
    def test_run(self, tmp_path):
        dataset_path = tmp_path / "dataset"
        class_one_number_events = 100
        class_one_config = {
            "target_path": "/target-one",
            "timestamps": [{"key": "source.field", "format": "%Y%M%d"}],
        }
        create_test_event_files(
            dataset_path,
            {"example": "event"},
            class_one_number_events,
            class_name="class_one",
            config=class_one_config,
        )
        class_two_number_events = 100
        class_two_config = {
            "target_path": "/target-two",
            "timestamps": [{"key": "source.field", "format": "%H%M%S"}],
        }
        create_test_event_files(
            dataset_path,
            {"example": "event"},
            class_two_number_events,
            class_name="class_two",
            config=class_two_config,
        )
        self.contoller.input.input_root_path = dataset_path
        self.contoller.input.temp_dir = tmp_path / "tmp_input_file"  # Mock temp dir for test
        os.makedirs(self.contoller.input._temp_dir, exist_ok=True)
        expected_status_code = 200
        responses.add(responses.POST, f"{self.target_url}/target-one", status=expected_status_code)
        responses.add(responses.POST, f"{self.target_url}/target-two", status=expected_status_code)
        statistics = self.contoller.run()
        total_events = class_one_number_events + class_two_number_events
        assert "Batch send time" in statistics
        assert isinstance(statistics["Batch send time"], float)
        assert statistics["Batch send time"] > 0
        del statistics["Batch send time"]  # delete here such that the next assertion is easier
        expected_statistics = {
            f"Requests http status {str(expected_status_code)}": total_events / self.batch_size,
            f"Events http status {str(expected_status_code)}": total_events,
        }
        assert statistics == expected_statistics
        assert len(responses.calls) == total_events / self.batch_size
        for call_id, call in enumerate(responses.calls):
            if call_id < (class_one_number_events / self.batch_size):
                assert (
                    call.request.url == f"{self.target_url}/target-one"
                ), f"Call {call_id} has wrong target"
            else:
                assert (
                    call.request.url == f"{self.target_url}/target-two"
                ), f"Call {call_id} has wrong target"
            expected_http_header = "application/x-ndjson; charset=utf-8"
            assert call.request.headers.get("Content-Type") == expected_http_header
            assert call.response.status_code == 200

    @mock.patch("logprep.event_generator.http.controller.ThreadPoolExecutor")
    def test_run_with_multiple_threads(self, mock_executor_class, tmp_path):
        self.contoller = Controller(
            input_dir="",
            batch_size=self.batch_size,
            replace_timestamp=True,
            tag="testdata",
            report=True,
            target_url=self.target_url,
            user="test-user",
            password="pass",
            thread_count=2,
        )
        dataset_path = tmp_path / "dataset"
        class_one_number_events = 100
        class_one_config = {
            "target_path": "/target-one",
            "timestamps": [{"key": "source.field", "format": "%Y%M%d"}],
        }
        create_test_event_files(
            dataset_path,
            {"example": "event"},
            class_one_number_events,
            class_name="class_one",
            config=class_one_config,
        )
        self.contoller.input.input_root_path = dataset_path
        mock_executor_instance = mock.MagicMock()
        mock_statistics = {
            "Events http status 200": 1,
            "Requests https status 200": 2,
            "Batch send time": 1,
        }
        mock_executor_instance.map.return_value = [mock_statistics]
        mock_executor_class.return_value.__enter__.return_value = mock_executor_instance
        stats = self.contoller.run()
        mock_executor_class.assert_called_with(max_workers=2)
        mock_executor_instance.map.assert_called()
        assert stats == mock_statistics
