"""This module contains functionality that allows to establish a connection with kafka."""

from functools import cached_property, partial
from typing import List
from copy import deepcopy
from datetime import datetime
import json
from socket import getfqdn
from attrs import validators, field, define
from confluent_kafka import Producer

from logprep.connector.connector_factory_error import InvalidConfigurationError
from logprep.abc.input import Input
from logprep.connector.confluent_kafka.common import (
    ConfluentKafka,
    ConfluentKafkaFactory,
    UnknownOptionError,
)
from logprep.connector.confluent_kafka.input import ConfluentKafkaInput
from logprep.abc.output import Output, CriticalOutputError
from logprep.util.validators import dict_with_keys_validator


class ConfluentKafkaOutputFactory(ConfluentKafkaFactory):
    """Create ConfluentKafka connector for output communication."""

    @staticmethod
    def create_from_configuration(configuration: dict) -> "ConfluentKafkaOutput":
        """Create a ConfluentKafkaOutput connector.

        Parameters
        ----------
        configuration : dict
           Parsed configuration YML.

        Returns
        -------
        kafka : ConfluentKafka
            Acts as input and output connector.

        Raises
        ------
        InvalidConfigurationError
            If ConfluentKafka configuration is invalid.

        """
        if not isinstance(configuration, dict):
            raise InvalidConfigurationError("Confluent Kafka: Configuration is not a dict!")

        try:
            kafka = ConfluentKafkaOutput(
                configuration["bootstrapservers"],
                configuration["producer"]["topic"],
                configuration["producer"]["error_topic"],
            )
        except KeyError as error:
            raise InvalidConfigurationError(
                f"Confluent Kafka: Missing configuration parameter " f"{str(error)}!"
            ) from error

        if "ssl" in configuration:
            ConfluentKafkaOutputFactory._set_ssl_options(kafka, configuration["ssl"])

        configuration = ConfluentKafkaOutputFactory._create_copy_without_base_options(configuration)

        try:
            kafka.set_option(configuration, "producer")
        except UnknownOptionError as error:
            raise InvalidConfigurationError(f"Confluent Kafka: {str(error)}") from error

        return kafka

    @staticmethod
    def _create_copy_without_base_options(configuration: dict) -> dict:
        config = deepcopy(configuration)
        del config["producer"]["topic"]
        del config["producer"]["error_topic"]
        ConfluentKafkaOutputFactory._remove_shared_base_options(config)

        return config


class ConfluentKafkaOutput(Output):
    """A kafka connector that serves as output connector."""

    @define(kw_only=True, slots=False)
    class Config(ConfluentKafkaInput.Config):
        """Confluent Kafka Output Config"""

        error_topic: str

    @cached_property
    def _client_id(self):
        return getfqdn()

    @property
    def _producer(self):
        return Producer(self._confluent_settings)

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

    def describe(self) -> str:
        """Get name of Kafka endpoint with the bootstrap server.

        Returns
        -------
        kafka : ConfluentKafka
            Acts as input and output connector.

        """
        base_description = super().describe()
        return f"{base_description} - Kafka Input: {self._config.bootstrapservers[0]}"

    def store(self, document: dict):
        """Store a document in the producer topic.

        Parameters
        ----------
        document : dict
           Document to store.

        """
        self.store_custom(document, self._config.topic)
        # TODO: Has to be done on pipeline level
        # if self._input:
        #     self._input.batch_finished_callback()

    def store_custom(self, document: dict, target: str):
        """Write document to Kafka into target topic.

        Parameters
        ----------
        document : dict
            Document to be stored in target topic.
        target : str
            Topic to store document in.
        Raises
        ------
        CriticalOutputError
            Raises if any error except a BufferError occurs while writing into Kafka.

        """
        try:
            self._producer.produce(
                target, value=json.dumps(document, separators=(",", ":")).encode("utf-8")
            )
            self._producer.poll(0)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config["producer"]["flush_timeout"])
        except BaseException as error:
            raise CriticalOutputError(
                f"Error storing output document: ({self._format_error(error)})", document
            ) from error

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        """Write errors into error topic for documents that failed processing.

        Parameters
        ----------
        error_message : str
           Error message to write into Kafka document.
        document_received : dict
            Document as it was before processing.
        document_processed : dict
            Document after processing until an error occurred.

        """
        value = {
            "error": error_message,
            "original": document_received,
            "processed": document_processed,
            "timestamp": str(datetime.now()),
        }
        try:
            self._producer.produce(
                self._config.error_topic,
                value=json.dumps(value, separators=(",", ":")).encode("utf-8"),
            )
            self._producer.poll(0)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config["producer"]["flush_timeout"])

    def shut_down(self):
        if self._producer is not None:
            self._producer.flush(self._config["producer"]["flush_timeout"])
            self._producer = None
