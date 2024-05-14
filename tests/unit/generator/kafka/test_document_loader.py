# pylint: disable=unused-argument
# pylint: disable=too-few-public-methods
# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=attribute-defined-outside-init
import re
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock, patch

from logprep.generator.kafka.document_loader import DocumentLoader
from logprep.generator.kafka.kafka_connector import KafkaConsumer
from logprep.generator.kafka.logger import create_logger
from tests.testdata.generator.kafka.kafka_config_dict import get_config


class MockedRecord:
    def __init__(self, value: str):
        self.record_value = value

    def value(self) -> Optional[str]:
        if self.record_value is None:
            return None
        return self.record_value.encode("utf-8")

    def error(self):
        return None


class MockedConsumer:
    def __init__(self, records: List[str]):
        self._records = records

    def poll(self, timeout: float):
        if len(self._records) == 0:
            return None
        return MockedRecord(self._records.pop())

    def get(self, _):
        return self._records.pop()


class TestDocumentLoader:
    def setup_method(self):
        config = get_config()
        logger = create_logger(config.logging_level)
        mocked_kafka = MagicMock()
        mocked_kafka.Consumer = MockedConsumer
        with patch("logprep.generator.kafka.kafka_connector.Consumer", return_value=mocked_kafka):
            self._document_loader = DocumentLoader(config, logger)

    def test_init(self):
        assert self._document_loader._source_count == 1
        assert self._document_loader._timeout == 1.0
        assert isinstance(self._document_loader._kafka_consumer, KafkaConsumer)

    def test_get_from_file(self):
        self._document_loader._source_file = Path(
            "tests/testdata/generator/kafka/wineventlog_raw.jsonl"
        )
        documents = self._document_loader._get_from_file()
        assert len(documents) == 500

    def test_get_raw_documents_from_file_if_source_file_set(self):
        self._document_loader._source_file = Path(
            "tests/testdata/generator/kafka/wineventlog_raw.jsonl"
        )
        documents = self._document_loader._get_raw_documents()
        assert len(documents) == 500

    def test_get_raw_documents_from_kafka_if_source_file_not_set(self):
        self._document_loader._source_file = None
        self._document_loader._source_count = 500
        self._document_loader._kafka_consumer._consumer = MockedConsumer(['{"foo": "bar"}'] * 250)
        documents = self._document_loader._get_raw_documents()
        assert len(documents) == 250

    def test_load_one_source_multiple_times(self):
        self._document_loader._kafka_consumer._consumer = MockedConsumer(
            ['{"foo": "1"}', '{"bar": "2"}']
        )
        documents = self._document_loader._get_from_kafka()
        assert documents == [{"bar": "2"}]

        documents = self._document_loader._get_from_kafka()
        assert documents == [{"foo": "1"}]

        documents = self._document_loader._get_from_kafka()
        assert not documents

    def test_load_multiple_source(self):
        self._document_loader._source_count = 5
        self._document_loader._kafka_consumer._consumer = MockedConsumer(['{"foo": "bar"}'] * 5)
        documents = self._document_loader._get_from_kafka()
        assert documents == [{"foo": "bar"}] * 5
        documents = self._document_loader._get_from_kafka()
        assert not documents

    def test_load_more_source_than_available(self):
        self._document_loader._source_count = 5
        self._document_loader._kafka_consumer._consumer = MockedConsumer(['{"foo": "bar"}'] * 2)
        documents = self._document_loader._get_from_kafka()
        assert documents == [{"foo": "bar"}] * 2

        documents = self._document_loader._get_from_kafka()
        assert not documents

    def test_get_documents_source_empty(self):
        self._document_loader._kafka_consumer._consumer = MockedConsumer([])
        documents = self._document_loader.get_documents()
        assert documents == []

    def test_get_documents_source_empty_dict(self):
        self._document_loader._kafka_consumer._consumer = MockedConsumer(["{}"])
        documents = self._document_loader.get_documents()
        assert len(documents) == 1
        for document in documents:
            assert re.match(
                r'{"_index": "load-tester", "tags": \["load-tester"\], '
                r'"@timestamp": "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", '
                r'"load-tester-unique": "',
                document,
            )

    def test_get_documents_source_multiple_times(self):
        self._document_loader._kafka_consumer._consumer = MockedConsumer(
            ['{"foo": "1"}', '{"bar": "2"}']
        )
        documents = self._document_loader.get_documents()
        assert len(documents) == 1
        for document in documents:
            assert re.match(
                r'{"bar": "2", "_index": "load-tester", "tags": \["load-tester"\], '
                r'"@timestamp": "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", '
                r'"load-tester-unique": "',
                document,
            )

        documents = self._document_loader.get_documents()
        assert len(documents) == 1
        for document in documents:
            assert re.match(
                r'{"foo": "1", "_index": "load-tester", "tags": \["load-tester"\], '
                r'"@timestamp": "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", '
                r'"load-tester-unique": "',
                document,
            )

        documents = self._document_loader.get_documents()
        assert documents == []

    def test_get_documents_multiple_source(self):
        self._document_loader._source_count = 5
        self._document_loader._kafka_consumer._consumer = MockedConsumer(['{"foo": "bar"}'] * 5)
        documents = self._document_loader.get_documents()
        assert len(documents) == 5
        for document in documents:
            assert re.match(
                r'{"foo": "bar", "_index": "load-tester", "tags": \["load-tester"\], '
                r'"@timestamp": "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", '
                r'"load-tester-unique": "',
                document,
            )

        documents = self._document_loader.get_documents()
        assert documents == []

    def test_get_documents_more_source_than_available(self):
        self._document_loader._source_count = 5
        self._document_loader._kafka_consumer._consumer = MockedConsumer(['{"foo": "bar"}'] * 2)
        documents = self._document_loader.get_documents()
        assert len(documents) == 2
        for document in documents:
            assert re.match(
                r'{"foo": "bar", "_index": "load-tester", "tags": \["load-tester"\], '
                r'"@timestamp": "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", '
                r'"load-tester-unique": "',
                document,
            )

        documents = self._document_loader.get_documents()
        assert documents == []
