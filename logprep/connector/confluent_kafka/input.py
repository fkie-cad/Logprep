# pylint: disable=line-too-long
"""
ConfluentkafkaInput
===================

Logprep uses `confluent-kafka` python client library to communicate with kafka-clusters.
Important documentation sources are:

- `the python client github page <https://github.com/confluentinc/confluent-kafka-python>`_
- `the python client api documentation <https://docs.confluent.io/current/clients/confluent-kafka-python/>`_
- `first steps documentation on confluent.io <https://docs.confluent.io/current/clients/python.html#>`_
- `underlying c-library documentation (librdkafka) <https://github.com/edenhill/librdkafka>`_

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
            group.id: "cgroup"
            enable.auto.commit: "true"
            session.timeout.ms: "6000"
            auto.offset.reset: "earliest"
"""
# pylint: enable=line-too-long
from functools import cached_property, partial
from logging import Logger
from socket import getfqdn
from typing import Callable, Optional, Tuple, Union

import msgspec
from attrs import define, field, validators
from confluent_kafka import (
    OFFSET_BEGINNING,
    OFFSET_END,
    OFFSET_INVALID,
    OFFSET_STORED,
    Consumer,
    KafkaException,
    TopicPartition,
)

from logprep.abc.connector import Connector
from logprep.abc.input import (
    CriticalInputError,
    CriticalInputParsingError,
    FatalInputError,
    Input,
    WarningInputError,
)
from logprep.util.validators import keys_in_validator

DEFAULTS = {
    "enable.auto.offset.store": "false",
    "enable.auto.commit": "true",
    "client.id": "<<hostname>>",
    "auto.offset.reset": "earliest",
    "session.timeout.ms": "6000",
    "statistics.interval.ms": "30000",
}


SPECIAL_OFFSETS = {
    OFFSET_BEGINNING,
    OFFSET_END,
    OFFSET_INVALID,
    OFFSET_STORED,
}


class ConfluentKafkaInput(Input):
    """A kafka input connector."""

    @define(kw_only=True, slots=False)
    class Metrics(Input.Metrics):
        """Metrics for ConfluentKafkaInput"""

        _prefix = "logprep_connector_input_kafka_"

        _stats: dict = field(factory=dict)
        """statistcs form librdkafka. Is filled by `_stats_callback`"""
        _commit_failures: int = 0
        """count of failed commits. Is filled by `_commit_callback`"""
        _commit_success: int = 0
        """count of successful commits. Is filled by `_commit_callback`"""
        _current_offsets: dict = field(factory=dict)
        """current offsets of the consumer. Is filled by `_get_raw_event`"""
        _committed_offsets: dict = field(factory=dict)
        """committed offsets of the consumer. Is filled by `_commit_callback`"""
        _consumer_group_id: str = ""
        """group id of the consumer. Is filled during initialization"""
        _consumer_client_id: str = ""
        """client id of the consumer. Is filled during initialization"""
        _consumer_topic: str = ""
        """topic of the consumer. Is filled during initialization"""

        @cached_property
        def _rdkafka_labels(self) -> str:
            client_id = self._consumer_client_id
            group_id = self._consumer_group_id
            topic = self._consumer_topic
            labels = {"client_id": client_id, "group_id": group_id, "topic": topic}
            labels = self._labels | labels
            labels = [":".join(item) for item in labels.items()]
            labels = ",".join(labels)
            return labels

        def _get_kafka_input_metrics(self) -> dict:
            exp = {
                f"{self._prefix}kafka_consumer_current_offset;"  # nosemgrep
                f"{self._rdkafka_labels},partition:{partition}": offset
                for partition, offset in self._current_offsets.items()
            }
            exp |= {
                f"{self._prefix}kafka_consumer_committed_offset;"  # nosemgrep
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
                f"{self._prefix}librdkafka_consumer_{stat};{self._rdkafka_labels}": value
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
            """overload of `expose` to add kafka specific metrics

            Returns
            -------
            dict
                metrics dictionary
            """
            exp = super().expose()
            labels = [":".join(item) for item in self._labels.items()]
            labels = ",".join(labels)
            exp |= self._get_top_level_metrics()
            exp |= self._get_cgrp_metrics()
            exp |= self._get_kafka_input_metrics()
            return exp

    @define(kw_only=True, slots=False)
    class Config(Input.Config):
        """Kafka input connector specific configurations"""

        topic: str = field(validator=validators.instance_of(str))
        """The topic from which new log messages will be fetched."""

        kafka_config: Optional[dict] = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
                partial(keys_in_validator, expected_keys=["bootstrap.servers", "group.id"]),
            ]
        )
        """ Kafka configuration for the kafka client. 
        At minimum the following keys must be set:
        
        - bootstrap.servers (STRING): a comma separated list of kafka brokers
        - group.id (STRING): a unique identifier for the consumer group
        
        For additional configuration options and their description see: 
        <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>
        
        .. datatemplate:import-module:: logprep.connector.confluent_kafka.input
            :template: defaults-renderer.tmpl

        """

    _last_valid_records: dict

    __slots__ = ["_last_valid_records"]

    def __init__(self, name: str, configuration: "Connector.Config", logger: Logger) -> None:
        super().__init__(name, configuration, logger)
        self._last_valid_records = {}
        self.metrics._consumer_group_id = self._config.kafka_config["group.id"]
        self.metrics._consumer_client_id = self._config.kafka_config.get("client.id", getfqdn())
        self.metrics._consumer_topic = self._config.topic

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
        DEFAULTS.update({"client.id": getfqdn()})
        self._config.kafka_config = DEFAULTS | self._config.kafka_config
        consumer = Consumer(self._config.kafka_config | injected_config)
        consumer.subscribe(
            [self._config.topic],
            on_assign=self._assign_callback,
            on_revoke=self._revoke_callback,
        )
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
            if topic_partition.offset not in SPECIAL_OFFSETS
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
        """Get next raw Message from Kafka.

        Parameters
        ----------
        timeout : float
           Timeout for obtaining a document from Kafka.

        Returns
        -------
        message_value : bytearray
            A raw document obtained from Kafka.

        Raises
        ------
        CriticalInputError
            Raises if an input is invalid or if it causes an error.
        """
        try:
            message = self._consumer.poll(timeout=timeout)
        except RuntimeError as error:
            raise FatalInputError(self, str(error)) from error
        if message is None:
            return None
        kafka_error = message.error()
        if kafka_error:
            raise CriticalInputError(
                self, "A confluent-kafka record contains an error code", kafka_error
            )
        self._last_valid_records[message.partition()] = message
        offset = {message.partition(): message.offset() + 1}
        self.metrics._current_offsets |= offset  # pylint: disable=protected-access
        return message.value()

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

    @property
    def _enable_auto_offset_store(self) -> bool:
        return self._config.kafka_config.get("enable.auto.offset.store") == "true"

    @property
    def _enable_auto_commit(self) -> bool:
        return self._config.kafka_config.get("enable.auto.commit") == "true"

    def batch_finished_callback(self) -> None:
        """Store offsets for each kafka partition in `self._last_valid_records`
        and if configured commit them. Should be called by output connectors if
        they are finished processing a batch of records.
        """
        if self._enable_auto_offset_store:
            return
        self._handle_offsets(self._consumer.store_offsets)
        if not self._enable_auto_commit:
            self._handle_offsets(self._consumer.commit)
        self._last_valid_records.clear()

    def _handle_offsets(self, offset_handler: Callable) -> None:
        for message in self._last_valid_records.values():
            try:
                offset_handler(message=message)
            except KafkaException:
                topic = self._consumer.list_topics(topic=self._config.topic)
                partition_keys = list(topic.topics[self._config.topic].partitions.keys())
                partitions = [
                    TopicPartition(self._config.topic, partition) for partition in partition_keys
                ]
                self._consumer.assign(partitions)
                offset_handler(message=message)

    def _assign_callback(self, consumer, topic_partitions):
        for topic_partition in topic_partitions:
            self._logger.info(
                f"{consumer.memberid()} was assigned to "
                f"topic: {topic_partition.topic} | "
                f"partition {topic_partition.partition}"
            )
            if topic_partition.offset in SPECIAL_OFFSETS:
                continue
            partition_offset = {
                topic_partition.partition: topic_partition.offset,
            }
            self.metrics._current_offsets |= partition_offset

    def _revoke_callback(self, consumer, topic_partitions):
        for topic_partition in topic_partitions:
            self._logger.warning(
                f"{consumer.memberid()} to be revoked from "
                f"topic: {topic_partition.topic} | "
                f"partition {topic_partition.partition}"
            )

    def _lost_callback(self, consumer, topic_partitions):
        for topic_partition in topic_partitions:
            self._logger.warning(
                f"{consumer.memberid()} has lost "
                f"topic: {topic_partition.topic} | "
                f"partition {topic_partition.partition}"
                "- try to reassign"
            )
            topic_partition.offset = OFFSET_STORED
        self._consumer.assign(topic_partitions)

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
