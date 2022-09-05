"""This module contains functionality that allows to obtain records from kafka."""

import json
from functools import cached_property, partial
from logging import Logger
from socket import getfqdn
from typing import Any, List, Union

from attrs import define, field, validators
from confluent_kafka import Consumer

from logprep.abc.connector import Connector
from logprep.abc.input import CriticalInputError, Input
from logprep.abc.output import Output
from logprep.connector.confluent_kafka.common import ConfluentKafkaFactory, UnknownOptionError
from logprep.connector.connector_factory_error import InvalidConfigurationError
from logprep.util.validators import dict_with_keys_validator


class ConfluentKafkaInputFactory(ConfluentKafkaFactory):
    """Create ConfluentKafka input connector for Logprep and input communication."""

    @staticmethod
    def create_from_configuration(configuration: dict) -> "ConfluentKafkaInput":
        """Create a ConfluentKafkaInput connector.

        Parameters
        ----------
        configuration : dict
           Parsed configuration YML.
        output_connector : Output
           Output connector to connect this output with.

        Returns
        -------
        kafka : ConfluentKafkaInput
            Acts as input connector.

        Raises
        ------
        InvalidConfigurationError
            If ConfluentKafkaInput configuration is invalid.

        """
        if not isinstance(configuration, dict):
            raise InvalidConfigurationError("Confluent Kafka Input: Configuration is not a dict!")

        try:
            kafka_input = ConfluentKafkaInput(
                configuration["bootstrapservers"],
                configuration["consumer"]["topic"],
                configuration["consumer"]["group"],
                configuration["consumer"].get("enable_auto_offset_store", False),
            )
        except KeyError as error:
            raise InvalidConfigurationError(
                f"Confluent Kafka Input: Missing configuration " f"parameter {str(error)}!"
            ) from error

        if "ssl" in configuration:
            ConfluentKafkaInputFactory._set_ssl_options(kafka_input, configuration["ssl"])

        configuration = ConfluentKafkaInputFactory._create_copy_without_base_options(configuration)

        try:
            kafka_input.set_option(configuration, "consumer")
        except UnknownOptionError as error:
            raise InvalidConfigurationError(f"Confluent Kafka Input: {str(error)}")

        return kafka_input


class ConfluentKafkaInput(Input):
    """A kafka input connector."""

    @define(kw_only=True, slots=False)
    class Config(Input.Config):
        """Common Configurations"""

        bootstrapservers: List[str]
        topic: str
        group: str
        enable_auto_offset_store: bool
        ssl: dict = field(
            validator=[
                validators.instance_of(dict),
                partial(
                    dict_with_keys_validator,
                    expected_keys=["cafile", "certfile", "keyfile", "password"],
                ),
            ],
            default={"cafile": None, "certfile": None, "keyfile": None, "password": None},
        )
        auto_commit: bool = field(validator=validators.instance_of(bool), default=True)
        session_timeout: int = field(validator=validators.instance_of(int), default=6000)
        offset_reset_policy: str = field(
            default="smallest",
            validator=validators.in_(["latest", "earliest", "none", "largest", "smallest"]),
        )

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
        return getfqdn()

    @property
    def _consumer(self):
        consumer = Consumer(self._confluent_settings)
        consumer.subscribe([self._config.topic])
        return consumer

    def describe(self) -> str:
        """Get name of Kafka endpoint with the bootstrap server.

        Returns
        -------
        kafka : ConfluentKafka
            Acts as input and output connector.

        """
        base_description = super().describe()
        return f"{base_description} - Kafka Input: {self._config.bootstrapservers[0]}"

    def _get_raw_event(self, timeout: float) -> bytearray:
        """Get next document from Kafka.

        Parameters
        ----------
        timeout : float
           Timeout for obtaining a document from Kafka.

        Returns
        -------
        json_dict : dict
            A document obtained from Kafka.

        Raises
        ------
        CriticalInputError
            Raises if an input is invalid or if it causes an error.

        """
        self._record = self._consumer.poll(timeout=timeout)
        if self._record is None:
            return None
        self._last_valid_records[self._record.partition()] = self._record
        self.current_offset = self._record.offset()
        record_error = self._record.error()
        if record_error:
            raise CriticalInputError(
                f"A confluent-kafka record contains an error code: ({record_error})", None
            )
        return self._record.value()

    def _get_event(self, timeout: float) -> Union[tuple[None, None], tuple[dict, dict]]:
        """Get next document from Kafka.

        Parameters
        ----------
        timeout : float
           Timeout for obtaining a document from Kafka.

        Returns
        -------
        json_dict : dict
            A document obtained from Kafka.

        Raises
        ------
        CriticalInputError
            Raises if an input is invalid or if it causes an error.

        """
        raw_event = self._get_raw_event(timeout)
        if raw_event is None:
            return None, None
        try:
            event_dict = json.loads(raw_event.decode("utf-8"))
        except ValueError as error:
            raise CriticalInputError(
                "Input record value is not a valid json string", raw_event
            ) from error
        if not isinstance(event_dict, dict):
            raise CriticalInputError("Input record value could not be parsed as dict", event_dict)
        return event_dict, raw_event

    @cached_property
    def _confluent_settings(self) -> dict:
        """generate confluence settings mapping

        Returns
        -------
        dict
            the translated confluence settings
        """
        configuration = {
            "bootstrap.servers": ",".join(self._config.bootstrapservers),
            "group.id": self._config.group,
            "enable.auto.commit": self._config.auto_commit,
            "session.timeout.ms": self._config.session_timeout,
            "enable.auto.offset.store": self._config.enable_auto_offset_store,
            "default.topic.config": {"auto.offset.reset": self._config.offset_reset_policy},
        }
        ssl_settings_are_setted = any(self._config.ssl[key] for key in self._config.ssl)
        if ssl_settings_are_setted:
            configuration.update(
                {
                    "security.protocol": "SSL",
                    "ssl.ca.location": self._config.ssl["cafile"],
                    "ssl.certificate.location": self._config.ssl["certfile"],
                    "ssl.key.location": self._config.ssl["keyfile"],
                    "ssl.key.password": self._config.ssl["password"],
                }
            )
        return configuration

    def batch_finished_callback(self):
        """Store offsets for each kafka partition.

        Should be called by output connectors if they are finished processing a batch of records.
        This is only used if automatic offest storing is disabled in the kafka input.

        The last valid record for each partition is be used by this method to update all offsets.

        """
        if not self._config.enable_auto_offset_store:
            if self._last_valid_records:
                for last_valid_records in self._last_valid_records.values():
                    self._consumer.store_offsets(message=last_valid_records)

    def shut_down(self):
        """Close consumer, which also commits kafka offsets."""
        if self._consumer is not None:
            self._consumer.close()
