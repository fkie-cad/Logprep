"""For loading documents from Kafka or from file and preparing them for sending"""

import json
from datetime import datetime, UTC
from logging import Logger
from typing import Any

from logprep.generator.kafka.configuration import Configuration
from logprep.generator.kafka.kafka_connector import KafkaConsumer


class DocumentLoader:
    """Loads documents from Kafka without increasing the offset and hold them in memory"""

    def __init__(self, config: Configuration, logger: Logger):
        self._logger = logger
        self._source_count = config.source_count
        self._source_file = config.source_file
        self._timeout = config.kafka.consumer.timeout
        self._kafka_consumer = KafkaConsumer(config.kafka)

    def _get_from_file(self) -> list[dict[Any, Any]]:
        with self._source_file.open("r", encoding="utf-8") as docs_file:
            input_docs: list[dict[Any, Any]] = [json.loads(doc) for doc in docs_file.readlines()]
            self._logger.info(f"Loaded {len(input_docs)} documents")
            return input_docs

    def _get_from_kafka(self) -> list[dict[Any, Any]]:
        documents = []
        cnt_invalid = 0
        for _ in range(self._source_count):
            try:
                doc = self._kafka_consumer.get(self._timeout)
            except json.decoder.JSONDecodeError:
                cnt_invalid += 1
                continue
            if doc is None:
                cnt_invalid += 1
                continue
            documents.append(doc)
        if cnt_invalid > 0:
            self._logger.warning(
                f"Fetched only {self._source_count - cnt_invalid} valid documents from "
                f"{self._source_count} source documents"
            )
        self._logger.info(f"Fetched {len(documents)} documents")
        return documents

    def get_documents(self) -> list[str]:
        """Get documents from Kafka format them so a unique value can be added easily"""
        docs_json = self._get_raw_documents()

        self._prepare_json_docs(docs_json)
        docs = [json.dumps(doc) for doc in docs_json]
        self._prepare_string_addition_of_additional_fields(docs)
        return docs

    def _get_raw_documents(self) -> list[dict[Any, Any]]:
        return self._get_from_file() if self._source_file else self._get_from_kafka()

    @staticmethod
    def _prepare_json_docs(docs: list[dict[Any, Any]], index_name: str = "load-tester") -> None:
        for doc in docs:
            doc["_index"] = index_name
            doc["tags"] = ["load-tester"]
            doc["@timestamp"] = datetime.now(UTC).isoformat()

    @staticmethod
    def _prepare_string_addition_of_additional_fields(docs: list[str]) -> None:
        """Prepare document for unique value that will be added on sending"""
        for idx, doc in enumerate(docs):
            if '"' in doc and doc.endswith("}"):
                docs[idx] = f'{doc[:-1]}, "load-tester-unique": "'

    def shut_down(self) -> None:
        """Shut down the Kafka consumer gracefully"""
        self._kafka_consumer.shut_down()
