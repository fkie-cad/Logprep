"""
ConfluentkafkaInput
===================

Logprep uses Confluent-Kafka-Python as client library to communicate with kafka-clusters.
Important information sources are `Confluent-Kafka-Python-Repo
<https://github.com/confluentinc/confluent-kafka-python>`_,
`Confluent-Kafka-Python-Doku 1 <https://docs.confluent.io/current/clients/confluent-kafka-python/>`_
(comprehensive but out-dated description),
`Confluent-Kafka-Python-Doku 2 <https://docs.confluent.io/current/clients/python.html#>`_
(currently just a brief description) and the C-library
`librdkafka <https://github.com/edenhill/librdkafka>`_, which is built on Confluent-Kafka-Python.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    input:
      mykafkainput:
        type: confluentkafka_input
        topic: consumer
        kafka_config:
            bootstrap.servers: "127.0.0.1:9092,127.0.0.1:9093"
            group: "cgroup"
            enable.auto.commit: "true"
            session.timeout.ms: "6000"
            auto.offset.reset: "earliest"
"""
from functools import cached_property
from logging import Logger
from socket import getfqdn
from typing import Callable, Optional, Tuple, Union

import msgspec
from attrs import define, field, validators
from confluent_kafka import Consumer, KafkaException, TopicPartition

from logprep.abc.connector import Connector
from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    Input,
    WarningInputError,
)

logprep_kafka_defaults = {
    "enable.auto.offset.store": "false",
    "enable.auto.commit": "true",
    "client.id": getfqdn(),
    "auto.offset.reset": "earliest",
    "session.timeout.ms": "6000",
    "statistics.interval.ms": "1000",
}


class ConfluentKafkaInput(Input):
    """A kafka input connector."""

    @define(kw_only=True, slots=False)
    class ConnectorMetrics(Input.ConnectorMetrics):
        """Metrics for ConfluentKafkaInput"""

        _prefix = "logprep_connector_input_kafka_"

        _stats: dict = field(factory=dict)
        """statistcs form librdkafka. Is filled by `_stats_callback`"""

        _commit_failures: int = 0

        _commit_success: int = 0

        _current_offsets: dict = field(factory=dict)

        _committed_offsets: dict = field(factory=dict)

        _consumer_group_id: str = ""

        _consumer_client_id: str = ""

        @cached_property
        def _rdkafka_labels(self) -> str:
            client_id = self._consumer_client_id
            group_id = self._consumer_group_id
            labels = {"client_id": client_id, "group_id": group_id}
            labels = self._labels | labels
            labels = [":".join(item) for item in labels.items()]
            labels = ",".join(labels)
            return labels

        def _get_kafka_input_metrics(self) -> dict:
            exp = {
                f"{self._prefix}kafka_consumer_current_offset;"
                f"{self._rdkafka_labels},partition:{partition}": offset
                for partition, offset in self._current_offsets.items()
            }
            exp |= {
                f"{self._prefix}kafka_consumer_committed_offset;"
                f"{self._rdkafka_labels},partition:{partition}": offset
                for partition, offset in self._committed_offsets.items()
            }
            exp.update(
                {
                    f"{self._prefix}kafka_consumer_commit_failures;"
                    f"{self._rdkafka_labels}": self._commit_failures,
                    f"{self._prefix}kafka_consumer_commit_success;"
                    f"{self._rdkafka_labels}": self._commit_success,
                }
            )
            return exp

        def _get_top_level_metrics(self) -> dict:
            return {
                f"{self._prefix}librdkafka_{stat};{self._rdkafka_labels}": value
                for stat, value in self._stats.items()
                if isinstance(value, (int, float))
            }

        def _get_cgrp_metrics(self) -> dict:
            exp = {}
            cgrp = self._stats.get("cgrp", {})
            for stat, value in cgrp.items():
                if isinstance(value, (int, float)):
                    exp[f"{self._prefix}librdkafka_cgrp_{stat};{self._rdkafka_labels}"] = value
            return exp

        def expose(self) -> dict:
            exp = super().expose()
            labels = [":".join(item) for item in self._labels.items()]
            labels = ",".join(labels)
            exp |= self._get_top_level_metrics()
            exp |= self._get_cgrp_metrics()
            exp |= self._get_kafka_input_metrics()
            return exp

    @define(kw_only=True, slots=False)
    class Config(Input.Config):
        """Kafka specific configurations"""

        topic: str = field(validator=validators.instance_of(str))
        """The topic from which new log messages will be fetched."""

        kafka_config: Optional[dict] = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
        )
        """ Kafka configuration for the kafka client. 
        At minimum the following keys must be set:
        - bootstrap.servers
        - group.id
        For possible configuration options see: 
        <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>
        """

    _last_valid_records: dict

    __slots__ = ["_last_valid_records"]

    def __init__(self, name: str, configuration: "Connector.Config", logger: Logger) -> None:
        super().__init__(name, configuration, logger)
        self.metric_labels = {"component": "kafka", "topic": self._config.topic}
        self._last_valid_records = {}
        self.metrics._consumer_group_id = self._config.kafka_config["group.id"]
        self.metrics._consumer_client_id = self._config.kafka_config.get("client.id", getfqdn())

    @cached_property
    def _consumer(self) -> Consumer:
        """configures and returns the consumer

        Returns
        -------
        Consumer
            confluent_kafka consumer object
        """
        injected_config = {
            "logger": self._logger,
            "on_commit": self._commit_callback,
            "stats_cb": self._stats_callback,
            "error_cb": self._error_callback,
        }
        self._config.kafka_config = logprep_kafka_defaults | self._config.kafka_config
        consumer = Consumer(self._config.kafka_config | injected_config)
        consumer.subscribe([self._config.topic])
        return consumer

    def _error_callback(self, error: KafkaException) -> None:
        """Callback for generic/global error events, these errors are typically
        to be considered informational since the client will automatically try to recover.
        This callback is served upon calling client.poll()

        Parameters
        ----------
        error : KafkaException
            the error that occurred
        """
        self._logger.warning(f"{self.describe()}: {error}")

    def _stats_callback(self, stats: str) -> None:
        """Callback for statistics data. This callback is triggered by poll()
        or flush every `statistics.interval.ms` (needs to be configured separately)

        Parameters
        ----------
        stats : str
            statistics from the underlying librdkafka library
            details about the data can be found here:
            https://github.com/confluentinc/librdkafka/blob/master/STATISTICS.md
        """
        self.metrics._stats = self._decoder.decode(stats)  # pylint: disable=protected-access

    def _commit_callback(
        self, error: Union[KafkaException, None], topic_partitions: list[TopicPartition]
    ) -> None:
        """Callback used to indicate success or failure of asynchronous and
        automatic commit requests. This callback is served upon calling consumer.poll()

        Parameters
        ----------
        error : KafkaException | None
            the commit error, or None on success
        topic_partitions : list[TopicPartition]
            partitions with their committed offsets or per-partition errors

        Raises
        ------
        WarningInputError
            if `error` is not None
        """
        if error is not None:
            self.metrics._commit_failures += 1
            raise WarningInputError(
                self, f"Could not commit offsets for {topic_partitions}: {error}"
            )
        self.metrics._commit_success += 1
        self.metrics._committed_offsets |= {
            topic_partition.partition: topic_partition.offset
            for topic_partition in topic_partitions
        }

    def describe(self) -> str:
        """Get name of Kafka endpoint and bootstrap servers.

        Returns
        -------
        kafka : str
            Description of the ConfluentKafkaInput connector.
        """
        base_description = super().describe()
        return f"{base_description} - Kafka Input: {self._config.kafka_config['bootstrap.servers']}"

    def _get_raw_event(self, timeout: float) -> bytearray:
        """Get next raw document from Kafka.

        Parameters
        ----------
        timeout : float
           Timeout for obtaining a document from Kafka.

        Returns
        -------
        record_value : bytearray
            A raw document obtained from Kafka.

        Raises
        ------
        CriticalInputError
            Raises if an input is invalid or if it causes an error.
        """
        try:
            record = self._consumer.poll(timeout=timeout)
        except RuntimeError as error:
            raise FatalInputError(self, str(error)) from error
        if record is None:
            return None
        record_error = record.error()
        self._last_valid_records[record.partition()] = record
        offset = {record.partition(): record.offset()}
        self.metrics._current_offsets |= offset  # pylint: disable=protected-access
        if record_error:
            raise CriticalInputError(
                self, "A confluent-kafka record contains an error code", record_error
            )
        return record.value()

    def _get_event(self, timeout: float) -> Union[Tuple[None, None], Tuple[dict, dict]]:
        """Parse the raw document from Kafka into a json.

        Parameters
        ----------
        timeout : float
           Timeout for obtaining a raw document from Kafka.

        Returns
        -------
        event_dict : dict
            A parsed document obtained from Kafka.
        raw_event : bytearray
            A raw document obtained from Kafka.

        Raises
        ------
        CriticalInputError
            Raises if an input is invalid or if it causes an error.
        """
        raw_event = self._get_raw_event(timeout)
        if raw_event is None:
            return None, None
        try:
            event_dict = self._decoder.decode(raw_event)
        except msgspec.DecodeError as error:
            raise CriticalInputParsingError(
                self, "Input record value is not a valid json string", raw_event
            ) from error
        return event_dict, raw_event

    def batch_finished_callback(self) -> None:
        """Store offsets for each kafka partition.
        Should be called by output connectors if they are finished processing a batch of records.
        Commits or stores the offset hold in `self._last_valid_records` for each partition.
        """
        if self._config.kafka_config.get("enable.auto.offset.store") == "true":
            return

        if self._config.kafka_config.get("enable.auto.commit") == "false":
            self._handle_offsets(self._consumer.commit)
            return

        self._handle_offsets(self._consumer.store_offsets)

    def _handle_offsets(self, offset_handler: Callable) -> None:
        for message in self._last_valid_records.values():
            try:
                offset_handler(message=message)
            except KafkaException:
                partitions = self._get_partitions()
                self._consumer.assign(partitions)
                offset_handler(message=message)

    def _get_partitions(self) -> list[TopicPartition]:
        topic = self._consumer.list_topics(topic=self._config.topic)
        partition_keys = list(topic.topics[self._config.topic].partitions.keys())
        partitions = [TopicPartition(self._config.topic, partition) for partition in partition_keys]

        return partitions

    def setup(self) -> None:
        super().setup()
        try:
            _ = self._consumer
        except (KafkaException, ValueError) as error:
            raise FatalInputError(self, str(error)) from error

    def shut_down(self) -> None:
        """Close consumer, which also commits kafka offsets."""
        self._consumer.close()
        super().shut_down()
