from logging import Handler
from os.path import join
from unittest.mock import patch

import pytest
import ujson

from logprep.connector.confluent_kafka import ConfluentKafkaFactory
from logprep.framework.pipeline import Pipeline, SharedCounter
from tests.acceptance.util import create_temporary_config_file_at_path
from tests.unit.connector.test_confluent_kafka import RecordMock


@pytest.fixture
def config():
    config_yml = {
        'process_count': 1,
        'timeout': 0.1,
        'profile_pipelines': False,
        'pipeline': [
            {
                'normalizername': {
                    'type': 'normalizer',
                    'specific_rules': ['tests/testdata/acceptance/normalizer/rules_static/specific'],
                    'generic_rules': ['tests/testdata/acceptance/normalizer/rules_static/generic'],
                    'regex_mapping': 'tests/testdata/acceptance/normalizer/rules_static/regex_mapping.yml'
                }
            }
        ],
        'connector': {
            'type': 'confluentkafka',
            'bootstrapservers': ['testserver:9092'],
            'consumer': {
                'topic': 'test_input_raw',
                'group': 'test_consumergroup',
                'auto_commit': False,
                'session_timeout': 654321,
                'enable_auto_offset_store': True,
                'offset_reset_policy': 'latest',
                'hmac': {
                    'target': "<RAW_MSG>",
                    'key': "secret",
                    'output_field': "hmac"
                }
            },
            'producer': {
                'topic': 'test_input_processed',
                'error_topic': 'test_error_producer',
                'ack_policy': '1',
                'compression': 'gzip',
                'maximum_backlog': 987654,
                'send_timeout': 2,
                'flush_timeout': 30,
                'linger_duration': 4321,
            }
        }
    }
    return config_yml


class SingleMessageConsumerJsonMock:

    def __init__(self, record):
        self.record = ujson.encode(record)

    def poll(self, timeout):
        return RecordMock(self.record, None)


class TmpFileProducerMock:

    def __init__(self, tmp_path):
        self.tmp_path = tmp_path

    def produce(self, target, value):
        with open(self.tmp_path, "wb") as f:
            f.write(value)

    def poll(self, _):
        ...


class TestFullHMACPassTest:

    def test_full_message_pass_with_hmac(self, tmp_path, config):
        config_path = str(tmp_path / 'generated_config.yml')
        create_temporary_config_file_at_path(config_path, config)

        with patch('logprep.connector.connector_factory.ConnectorFactory.create') as mock_connector_factory:
            input_test_event = {"test": "message"}
            expected_output_event = {
                'test': 'message',
                'hmac': {
                    'hmac': '5a77054b5f1d9ea60000520a4e2cf661e7a11de4205ca70c6977fc8040076a6e',
                    'compressed_base64': 'eJyrVipJLS5RslLKTS0uTkxPVaoFADwCBmA='
                }
            }

            # create kafka connector manually and add custom mock consumer and mock producer objects
            kafka = ConfluentKafkaFactory.create_from_configuration(config['connector'])
            kafka._consumer = SingleMessageConsumerJsonMock(input_test_event)
            output_file_path = join(tmp_path, "kafka_out.txt")
            kafka._producer = TmpFileProducerMock(output_file_path)
            mock_connector_factory.return_value = (kafka, kafka)

            # Create and setup logprep pipeline
            pipeline = Pipeline(config['connector'], config['pipeline'], config['timeout'],
                                SharedCounter(), Handler(), 300, 1800, dict())
            pipeline._setup()

            # execute full logprep pipeline call
            pipeline._retrieve_and_process_data()

            # read logprep kafka output from mocked kafka file producer
            with open(output_file_path, "rb") as f:
                content = ujson.loads(f.read())

            # compare logprep output with expected output
            assert content == expected_output_event
