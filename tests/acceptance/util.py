#!/usr/bin/python3
# pylint: disable=protected-access
# pylint: disable=missing-docstring
import json
from copy import deepcopy
from logging import getLogger, DEBUG, basicConfig, Handler
from multiprocessing import Lock
from os import path, makedirs
from os.path import join

from logprep.connector.confluent_kafka import ConfluentKafkaFactory
from logprep.framework.pipeline import Pipeline, SharedCounter
from logprep.util.helper import recursive_compare, remove_file_if_exists
from logprep.util.json_handling import parse_jsonl
from logprep.util.rule_dry_runner import get_patched_runner
from tests.unit.connector.test_confluent_kafka import RecordMock

basicConfig(level=DEBUG, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s")
logger = getLogger("Logprep-Test")


def get_difference(test_output, expected_output):
    for idx, _ in enumerate(test_output):
        test_event = deepcopy(test_output[idx])
        expected_event = deepcopy(expected_output[idx])
        difference = recursive_compare(test_event, expected_event)
        if difference:
            return {"event_line_no": idx, "difference": difference}
    return {"event_line_no": None, "difference": (None, None)}


def store_latest_test_output(target_output_identifier, output_of_test):
    """Store output for test.

    This can be used to create expected outputs for new rules.
    The resulting file can be used as it is.

    """

    output_dir = "tests/testdata/out"
    latest_output_path = path.join(output_dir, f"latest_{target_output_identifier}.out")

    if not path.exists(output_dir):
        makedirs(output_dir)

    with open(latest_output_path, "w", encoding="utf-8") as latest_output:
        for test_output_line in output_of_test:
            latest_output.write(json.dumps(test_output_line) + "\n")


def get_test_output(config_path):
    patched_runner = get_patched_runner(config_path, logger)

    test_output_path = patched_runner._configuration["connector"]["output_path"]
    remove_file_if_exists(test_output_path)

    patched_runner.start()
    parsed_test_output = parse_jsonl(test_output_path)

    remove_file_if_exists(test_output_path)

    return parsed_test_output


def assert_result_equal_expected(config, expected_output, tmp_path):
    ...


class SingleMessageConsumerJsonMock:
    def __init__(self, record):
        self.record = json.dumps(record, separators=(",", ":"))

    # pylint: disable=unused-argument
    def poll(self, timeout):
        return RecordMock(self.record, None)

    # pylint: enable=unused-argument


class TmpFileProducerMock:
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path

    def produce(self, target, value):
        with open(self.tmp_path, "a", encoding="utf-8") as tmp_file:
            tmp_file.write(f"{target} {value.decode()}\n")

    def poll(self, _):
        ...


def mock_kafka_and_run_pipeline(config, input_test_event, mock_connector_factory, tmp_path):
    # create kafka connector manually and add custom mock consumer and mock producer objects
    kafka = ConfluentKafkaFactory.create_from_configuration(config["connector"])
    kafka._consumer = SingleMessageConsumerJsonMock(input_test_event)
    output_file_path = join(tmp_path, "kafka_out.txt")
    kafka._producer = TmpFileProducerMock(output_file_path)
    mock_connector_factory.return_value = (kafka, kafka)

    # Create, setup and execute logprep pipeline
    pipeline_index = 1
    pipeline = Pipeline(
        pipeline_index,
        config["connector"],
        config["pipeline"],
        {},
        config["timeout"],
        SharedCounter(),
        Handler(),
        Lock(),
        {},
    )
    pipeline._setup()
    pipeline._retrieve_and_process_data()

    return output_file_path


def get_default_logprep_config(pipeline_config, with_hmac=True):
    config_yml = {
        "process_count": 1,
        "timeout": 0.1,
        "profile_pipelines": False,
        "pipeline": pipeline_config,
        "connector": {
            "type": "confluentkafka",
            "bootstrapservers": ["testserver:9092"],
            "consumer": {
                "topic": "test_input_raw",
                "group": "test_consumergroup",
                "auto_commit": False,
                "session_timeout": 654321,
                "enable_auto_offset_store": True,
                "offset_reset_policy": "latest",
            },
            "producer": {
                "topic": "test_input_processed",
                "error_topic": "test_error_producer",
                "ack_policy": "1",
                "compression": "gzip",
                "maximum_backlog": 987654,
                "send_timeout": 2,
                "flush_timeout": 30,
                "linger_duration": 4321,
            },
        },
    }

    if with_hmac:
        config_yml["connector"]["consumer"]["hmac"] = {
            "target": "<RAW_MSG>",
            "key": "secret",
            "output_field": "hmac",
        }

    return config_yml
