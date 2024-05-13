# pylint: disable=unused-argument
# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=attribute-defined-outside-init
import json
from unittest import mock
from unittest.mock import MagicMock, patch

from logprep.generator.kafka.document_sender import DocumentSender
from logprep.generator.kafka.kafka_connector import KafkaProducer
from tests.testdata.generator.kafka.kafka_config_dict import get_config


class MockedProducer:
    def __init__(self):
        self.produced = []

    def produce(self, _, value):
        self.produced.append(json.loads(value))

    def poll(self, timeout): ...

    def flush(self, timeout): ...


class TestDocumentSender:
    def setup_method(self):
        mocked_kafka = MagicMock()
        mocked_kafka.Producer = MockedProducer
        with patch("logprep.generator.kafka.kafka_connector.Producer", return_value=mocked_kafka):
            self._document_sender = DocumentSender(get_config(), MagicMock())

    def test_init(self):
        assert isinstance(self._document_sender._kafka_producer, KafkaProducer)

    @mock.patch("logprep.generator.kafka.document_sender.perf_counter")
    def test_send_zero(self, time_mock):
        time_mock.return_value = 0
        self._document_sender._kafka_producer._producer = MockedProducer()
        count = self._document_sender.send(
            0, ['{"foo": "1", "added": "', '{"bar": "2", "added": "']
        )
        assert count == 0
        assert self._document_sender._kafka_producer._producer.produced == []

    @mock.patch("logprep.generator.kafka.document_sender.perf_counter")
    def test_send_one_of_zero(self, time_mock):
        time_mock.return_value = 0
        self._document_sender._kafka_producer._producer = MockedProducer()
        count = self._document_sender.send(1, [])
        assert count == 0
        assert self._document_sender._kafka_producer._producer.produced == []

    @mock.patch("logprep.generator.kafka.document_sender.perf_counter")
    def test_send_one(self, time_mock):
        time_mock.return_value = 0
        self._document_sender._kafka_producer._producer = MockedProducer()
        count = self._document_sender.send(
            1, ['{"foo": "1", "added": "', '{"bar": "2", "added": "']
        )
        assert count == 1
        self._assert_uuid4_was_added_and_remove_it()
        assert self._document_sender._kafka_producer._producer.produced == [{"foo": "1"}]

    @mock.patch("logprep.generator.kafka.document_sender.perf_counter")
    def test_send_multiple(self, time_mock):
        time_mock.return_value = 0
        self._document_sender._kafka_producer._producer = MockedProducer()
        count = self._document_sender.send(
            2, ['{"foo": "1", "added": "', '{"bar": "2", "added": "']
        )
        assert count == 2
        self._assert_uuid4_was_added_and_remove_it()
        assert self._document_sender._kafka_producer._producer.produced == [
            {"foo": "1"},
            {"bar": "2"},
        ]

    @mock.patch("logprep.generator.kafka.document_sender.perf_counter")
    def test_send_more_than_available(self, time_mock):
        time_mock.return_value = 0
        self._document_sender._kafka_producer._producer = MockedProducer()
        count = self._document_sender.send(
            3, ['{"foo": "1", "added": "', '{"bar": "2", "added": "']
        )
        assert count == 3
        self._assert_uuid4_was_added_and_remove_it()
        assert self._document_sender._kafka_producer._producer.produced == [
            {"foo": "1"},
            {"bar": "2"},
            {"foo": "1"},
        ]

    def _assert_uuid4_was_added_and_remove_it(self):
        for produced in self._document_sender._kafka_producer._producer.produced:
            assert len(produced.get("added", "")) == 36
            del produced["added"]
