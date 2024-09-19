# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import os
from unittest import mock

import pytest
import responses

from logprep.generator.http.controller import Controller
from tests.unit.generator.http.util import create_test_event_files


class TestController:
    def setup_method(self):
        self.target_url = "http://testendpoint"
        self.batch_size = 10
        self.controller = Controller(
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

    # @pytest.mark.skip(reason="This test blocks and has to be fixed")  # TODO: Fix this test
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
        self.controller.input.input_root_path = dataset_path
        self.controller.input.temp_dir = tmp_path / "tmp_input_file"  # Mock temp dir for test
        os.makedirs(self.controller.input._temp_dir, exist_ok=True)
        expected_status_code = 200
        responses.add(responses.POST, f"{self.target_url}/target-one", status=expected_status_code)
        responses.add(responses.POST, f"{self.target_url}/target-two", status=expected_status_code)
        self.controller.run()

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

    @mock.patch("logprep.generator.http.controller.ThreadPoolExecutor")
    def test_run_with_multiple_threads(self, mock_executor_class, tmp_path):
        self.controller = Controller(
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
        self.controller.input.input_root_path = dataset_path
        mock_executor_instance = mock.MagicMock()
        mock_executor_class.return_value.__enter__.return_value = mock_executor_instance
        self.controller.run()
        mock_executor_class.assert_called_with(max_workers=2)
        mock_executor_instance.map.assert_called()
