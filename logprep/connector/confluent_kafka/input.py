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
from typing import Any, Optional, Tuple, Union

import msgspec
from attrs import define, field, validators
from confluent_kafka import Consumer, KafkaException, TopicPartition

from logprep.abc.input import CriticalInputError, CriticalInputParsingError, Input
from logprep.abc.output import FatalOutputError


class ConfluentKafkaInput(Input):
    """A kafka input connector."""

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
            factory=dict,
        )
        """ Kafka configuration for the kafka client. 
        At minimum the following keys must be set:
        - bootstrap.servers
        - group.id
        For possible configuration options see: 
        <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>
        """

    current_offset: int

    _record: Any

    _last_valid_records: dict

    __slots__ = [
        "current_offset",
        "_record",
        "_last_valid_records",
    ]

    def __init__(self, name: str, configuration: "Connector.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self._last_valid_records = {}
        self._record = None

    @cached_property
    def _client_id(self):
        """Return the client id"""
        return getfqdn()

    @cached_property
    def _consumer(self):
        """Create and return a new confluent kafka consumer"""
        consumer = Consumer(self._config.kafka_config)
        consumer.subscribe([self._config.topic])
        return consumer

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
        self._record = self._consumer.poll(timeout=timeout)
        while self._record is None:
            self._record = self._consumer.poll(timeout=timeout)
        self._last_valid_records[self._record.partition()] = self._record
        self.current_offset = self._record.offset()
        record_error = self._record.error()
        if record_error:
            raise CriticalInputError(
                self, "A confluent-kafka record contains an error code", record_error
            )
        return self._record.value()

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
        if not self._config.enable_auto_offset_store:
            if self._last_valid_records:
                for last_valid_records in self._last_valid_records.values():
                    try:
                        self._consumer.store_offsets(message=last_valid_records)
                    except KafkaException:
                        topic = self._consumer.list_topics(topic=self._config.topic)
                        partition_keys = list(topic.topics[self._config.topic].partitions.keys())
                        partitions = [
                            TopicPartition(self._config.topic, partition)
                            for partition in partition_keys
                        ]
                        self._consumer.assign(partitions)
                        self._consumer.store_offsets(message=last_valid_records)

    def setup(self):
        super().setup()
        try:
            _ = self._consumer
        except (KafkaException, ValueError) as error:
            raise FatalOutputError(self, str(error)) from error

    def shut_down(self):
        """Close consumer, which also commits kafka offsets."""
        if self._consumer is not None:
            self._consumer.close()
