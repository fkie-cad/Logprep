# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import json
import os
from unittest import mock

import responses

from logprep.generator.confluent_kafka.controller import KafkaController
from tests.unit.generator.http.util import create_test_event_files


@mock.patch("logprep.generator.http.controller.Factory.create")
def test_kafka_controller_create_output(mock_factory_create):

    kwargs = {
        "input_dir": "/some-path",
        "output_config": '{"bootstrap.servers": "localhost:9092"}',
    }

    expected_output_config = {
        "generator_output": {
            "type": "confluentkafka_output",
            "topic": "producer",
            "kafka_config": json.loads(kwargs.get("output_config")),
        },
    }
    controller = KafkaController(**kwargs)
    mock_factory_create.assert_called_once_with(expected_output_config)

    assert controller.output == mock_factory_create.return_value


class TestController:
    def setup_method(self):
        self.target_url = "http://testendpoint"
        self.batch_size = 10

        self.controller = KafkaController(
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
