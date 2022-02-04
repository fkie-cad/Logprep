"""This module contains functionality that allows to establish a connection with kafka."""

from typing import List
from copy import deepcopy
from datetime import datetime
import ujson
from socket import getfqdn

from confluent_kafka import Producer

from logprep.connector.connector_factory_error import InvalidConfigurationError
from logprep.input.input import Input
from logprep.connector.confluent_kafka_shared import (
    ConfluentKafka,
    ConfluentKafkaFactory,
    UnknownOptionError,
)
from logprep.output.output import Output, CriticalOutputError


class ConfluentKafkaOutputFactory(ConfluentKafkaFactory):
    """Create ConfluentKafka connectors for logprep and input/output communication."""

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
            raise InvalidConfigurationError(f"Confluent Kafka: {str(error)}")

        return kafka

    @staticmethod
    def _create_copy_without_base_options(configuration: dict) -> dict:
        config = deepcopy(configuration)
        del config["producer"]["topic"]
        del config["producer"]["error_topic"]
        ConfluentKafkaOutputFactory._remove_shared_base_options(config)

        return config


class ConfluentKafkaOutput(Output, ConfluentKafka):
    """A kafka connector that serves as both input and output connector."""

    def __init__(
        self, bootstrap_servers: List[str], producer_topic: str, producer_error_topic: str
    ):
        ConfluentKafka.__init__(self, bootstrap_servers)
        self._producer_topic = producer_topic
        self._producer_error_topic = producer_error_topic
        self._input = None

        self._config["producer"] = {
            "ack_policy": "all",
            "compression": "none",
            "maximum_backlog": 10 * 1000,
            "linger_duration": 0,
            "send_timeout": 0,
            "flush_timeout": 30.0,  # may require adjustment
        }

        self._client_id = getfqdn()
        self._producer = None

    def connect_input(self, input_connector: Input):
        """Connect input connector.

        This connector is used for callbacks.

        Parameters
        ----------
        input_connector : Input
           Input connector to connect this output with.
        """
        self._input = input_connector

    def describe_endpoint(self) -> str:
        """Get name of Kafka endpoint with the bootstrap server.

        Returns
        -------
        kafka : ConfluentKafka
            Acts as input and output connector.

        """
        return f"Kafka Output: {self._bootstrap_servers[0]}"

    def store(self, document: dict):
        """Store a document in the producer topic.

        Parameters
        ----------
        document : dict
           Document to store.

        """
        self.store_custom(document, self._producer_topic)
        if self._input:
            self._input.batch_finished_callback()

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
        if self._producer is None:
            self._create_producer()

        try:
            self._producer.produce(target, value=ujson.dumps(document).encode("utf-8"))
            self._producer.poll(0)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config["producer"]["flush_timeout"])
        except BaseException as error:
            raise CriticalOutputError(
                "Error storing output document: ({})".format(self._format_message(error)), document
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
        if self._producer is None:
            self._create_producer()

        value = {
            "error": error_message,
            "original": document_received,
            "processed": document_processed,
            "timestamp": str(datetime.now()),
        }
        try:
            self._producer.produce(
                self._producer_error_topic, value=ujson.dumps(value).encode("utf-8")
            )
            self._producer.poll(0)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config["producer"]["flush_timeout"])

    def _create_producer(self):
        self._producer = Producer(self._create_confluent_settings())

    def _create_confluent_settings(self):
        configuration = {
            "acks": self._config["producer"]["ack_policy"],
            "compression.type": self._config["producer"]["compression"],
            "queue.buffering.max.messages": self._config["producer"]["maximum_backlog"],
            "linger.ms": self._config["producer"]["linger_duration"],
        }
        self._set_base_confluent_settings(configuration)

        return configuration

    def shut_down(self):
        if self._producer is not None:
            self._producer.flush(self._config["producer"]["flush_timeout"])
            self._producer = None
