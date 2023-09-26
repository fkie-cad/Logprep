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
from typing import Optional, Tuple, Union

import msgspec
from attrs import define, field, validators
from confluent_kafka import Consumer, KafkaException, TopicPartition

from logprep.abc.connector import Connector
from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    Input,
    WarningInputError,
)
from logprep.abc.output import FatalOutputError

logprep_kafka_defaults = {
    "enable.auto.offset.store": "false",
    "enable.auto.commit": "true",
    "client.id": getfqdn(),
    "auto.offset.reset": "earliest",
    "session.timeout.ms": "6000",
}


class ConfluentKafkaInput(Input):
    """A kafka input connector."""

    @define(kw_only=True)
    class ConnectorMetrics(Input.ConnectorMetrics):
        """Metrics for ConfluentKafkaInput"""

        _prefix = "logprep_connector_input_kafka_"

        commit_failures: int = 0

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

    __slots__ = [
        "_last_valid_records",
    ]

    def __init__(self, name: str, configuration: "Connector.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self._last_valid_records = {}

    @cached_property
    def _consumer(self) -> Consumer:
        """Create and return a new confluent kafka consumer"""
        injected_config = {
            "logger": self._logger,
            "on_commit": self._commit_callback,
        }
        self._config.kafka_config = logprep_kafka_defaults | self._config.kafka_config
        consumer = Consumer(self._config.kafka_config | injected_config)
        consumer.subscribe([self._config.topic])
        return consumer

    def _commit_callback(
        self, error: KafkaException | None, topic_partitions: list[TopicPartition]
    ):
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
            self.metrics.commit_failures += 1
            raise WarningInputError(
                self, f"Could not commit offsets for {topic_partitions}: {error}"
            )

    def describe(self) -> str:
        """Get name of Kafka endpoint and the first bootstrap server.

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
        record = self._consumer.poll(timeout=timeout)
        if record is None:
            return None
        self._last_valid_records[record.partition()] = record
        record_error = record.error()
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
        if not isinstance(event_dict, dict):
            raise CriticalInputParsingError(
                self, "Input record value could not be parsed as dict", event_dict
            )
        return event_dict, raw_event

    def batch_finished_callback(self):
        """Store offsets for each kafka partition.
        Should be called by output connectors if they are finished processing a batch of records.
        This is only used if automatic offest storing is disabled in the kafka input.
        The last valid record for each partition is be used by this method to update all offsets.
        """
        if self._config.kafka_config.get("enable.auto.commit") == "false":
            for message in self._last_valid_records.values():
                self._consumer.commit(message=message, asynchronous=True)
            return

        if self._config.kafka_config.get("enable.auto.offset.store") == "true":
            return

        for message in self._last_valid_records.values():
            try:
                self._consumer.store_offsets(message=message)
            except KafkaException:
                topic = self._consumer.list_topics(topic=self._config.topic)
                partition_keys = list(topic.topics[self._config.topic].partitions.keys())
                partitions = [
                    TopicPartition(self._config.topic, partition) for partition in partition_keys
                ]
                self._consumer.assign(partitions)
                self._consumer.store_offsets(message=message)

    def setup(self):
        super().setup()
        try:
            _ = self._consumer
        except (KafkaException, ValueError) as error:
            raise FatalOutputError(self, str(error)) from error

    def shut_down(self):
        """Close consumer, which also commits kafka offsets."""
        self._consumer.close()
        super().shut_down()
