# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import os

import responses

from logprep.generator.factory import ControllerFactory
from tests.unit.generator.http.util import create_test_event_files


class TestKafkaController:

    def setup_method(self):
        self.target_url = "http://testendpoint"
        self.batch_size = 10

        self.controller = ControllerFactory.create(
            target="kafka",
            input_dir="",
            output_config='{"bootstrap.servers": "localhost:9092"}',
            batch_size=self.batch_size,
            replace_timestamp=True,
            tag="testdata",
            report=True,
            user="test-user",
            password="pass",
            thread_count=1,
            kafka_output=None,
        )

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
