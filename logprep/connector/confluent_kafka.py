"""This module contains functionality that allows to establish a connection with kafka."""
import hashlib
from base64 import b64encode
from copy import deepcopy
from datetime import datetime
from hmac import HMAC
from socket import getfqdn
from typing import List, Optional
from zlib import compress

import json
from confluent_kafka import Consumer, Producer

from logprep.connector.connector_factory_error import InvalidConfigurationError
from logprep.input.input import Input, CriticalInputError
from logprep.output.output import Output, CriticalOutputError
from logprep.util.helper import add_field_to, get_dotted_field_value


class ConfluentKafkaError(BaseException):
    """Base class for ConfluentKafka related exceptions."""


class UnknownOptionError(ConfluentKafkaError):
    """Raise if an invalid option has been set in the ConfluentKafka configuration."""


class InvalidMessageError(ConfluentKafkaError):
    """Raise if an invalid message has been received by ConfluentKafka."""


class ConfluentKafkaFactory:
    """Create ConfluentKafka connectors for logprep and input/output communication."""

    @staticmethod
    def create_from_configuration(configuration: dict) -> "ConfluentKafka":
        """Create a ConfluentKafka connector.

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
        logprep.connector.connector_factory_error.InvalidConfigurationError
            If ConfluentKafka configuration is invalid.

        """
        if not isinstance(configuration, dict):
            raise InvalidConfigurationError("Confluent Kafka: Configuration is not a dict!")

        try:
            kafka = ConfluentKafka(
                configuration["bootstrapservers"],
                configuration["consumer"]["topic"],
                configuration["consumer"]["group"],
                configuration["consumer"].get("enable_auto_offset_store", True),
                configuration["producer"]["topic"],
                configuration["producer"]["error_topic"],
            )
        except KeyError as error:
            raise InvalidConfigurationError(
                f"Confluent Kafka: Missing configuration parameter " f"{str(error)}!"
            ) from error

        if "ssl" in configuration:
            ConfluentKafkaFactory._set_ssl_options(kafka, configuration["ssl"])

        configuration = ConfluentKafkaFactory._create_copy_without_base_options(configuration)

        try:
            kafka.set_option(configuration)
        except UnknownOptionError as error:
            raise InvalidConfigurationError(f"Confluent Kafka: {str(error)}") from error

        return kafka

    @staticmethod
    def _set_ssl_options(kafka: "ConfluentKafka", ssl_config: dict):
        ssl_keys = ["cafile", "certfile", "keyfile", "password"]
        if not any((i in ssl_config for i in ssl_keys)):
            return

        cafile = ssl_config["cafile"] if "cafile" in ssl_config else None
        certfile = ssl_config["certfile"] if "certfile" in ssl_config else None
        keyfile = ssl_config["keyfile"] if "keyfile" in ssl_config else None
        password = ssl_config["password"] if "password" in ssl_config else None

        kafka.set_ssl_config(cafile, certfile, keyfile, password)

    @staticmethod
    def _create_copy_without_base_options(configuration: dict) -> dict:
        config = deepcopy(configuration)
        del config["type"]
        del config["bootstrapservers"]
        del config["consumer"]["topic"]
        del config["consumer"]["group"]
        del config["producer"]["topic"]
        del config["producer"]["error_topic"]

        if "ssl" in config:
            del config["ssl"]

        return config

    @staticmethod
    def _set_if_exists(key: str, config: dict, kafka_setter):
        if key in config:
            kafka_setter(config[key])


class ConfluentKafka(Input, Output):
    """A kafka connector that serves as both input and output connector."""

    def __init__(
        self,
        bootstrap_servers: List[str],
        consumer_topic: str,
        consumer_group: str,
        enable_auto_offset_store: bool,
        producer_topic: str,
        producer_error_topic: str,
    ):
        self._bootstrap_servers = bootstrap_servers
        self._consumer_topic = consumer_topic
        self._consumer_group = consumer_group
        self._producer_topic = producer_topic
        self._producer_error_topic = producer_error_topic

        self.current_offset = -1

        self._config = {
            "ssl": {"cafile": None, "certfile": None, "keyfile": None, "password": None},
            "consumer": {
                "auto_commit": True,
                "session_timeout": 6000,
                "offset_reset_policy": "smallest",
                "enable_auto_offset_store": enable_auto_offset_store,
                "hmac": {"target": "", "key": "", "output_field": ""},
            },
            "producer": {
                "ack_policy": "all",
                "compression": "none",
                "maximum_backlog": 10 * 1000,
                "linger_duration": 0,
                "send_timeout": 0,
                "flush_timeout": 30.0,  # may require adjustment
            },
        }

        self._flush_timeout = 0.01  # may require adjustment

        self._client_id = getfqdn()
        self._consumer = None
        self._producer = None

        self._record = None

        self._add_hmac = False

        self._enable_auto_offset_store = enable_auto_offset_store

    def describe_endpoint(self) -> str:
        """Get name of Kafka endpoint with the bootstrap server.

        Returns
        -------
        kafka : ConfluentKafka
            Acts as input and output connector.

        """
        return "Kafka: " + str(self._bootstrap_servers[0])

    def set_ssl_config(self, cafile: str, certfile: str, keyfile: str, password: str):
        """Set SSL configuration for kafka.

        Parameters
        ----------
        cafile : str
           Path to certificate authority file.
        certfile : str
           Path to certificate file.
        keyfile : str
           Path to private key file.
        password : str
           Password for private key.

        """
        self._config["ssl"]["cafile"] = cafile
        self._config["ssl"]["certfile"] = certfile
        self._config["ssl"]["keyfile"] = keyfile
        self._config["ssl"]["password"] = password

    def set_option(self, new_options: dict):
        """Set configuration options for kafka.

        Parameters
        ----------
        new_options : dict
           New options to set.

        Raises
        ------
        UnknownOptionError
            Raises if an option is invalid.

        """

        valid_hmac_options = set(self._config.get("consumer", {}).get("hmac", {}).keys())

        for key in new_options:
            if key not in self._config:
                raise UnknownOptionError(f"Unknown Option: {key}")
            if isinstance(new_options[key], dict):
                for subkey in new_options[key]:
                    if subkey not in self._config[key]:
                        raise UnknownOptionError(f"Unknown Option: {key}/{subkey}")
                    self._config[key][subkey] = new_options[key][subkey]

        # validate hmac subfields
        if new_options.get("consumer", {}).get("hmac", None) is not None:
            new_hmac_options_keys = set(new_options.get("consumer", {}).get("hmac").keys())
            unknown_options = new_hmac_options_keys.difference(valid_hmac_options)
            if unknown_options:
                raise UnknownOptionError(f"Unknown Hmac Options: {unknown_options}")

            missing_options = valid_hmac_options.difference(new_hmac_options_keys)
            if missing_options:
                raise InvalidConfigurationError(f"Hmac option(s) missing: {missing_options}")

            for key in valid_hmac_options:
                config_value = self._config["consumer"]["hmac"][key]
                if not isinstance(config_value, str):
                    raise InvalidConfigurationError(
                        f"Hmac option '{key}' has wrong type: '{type(config_value)}', "
                        f"expected 'str'"
                    )
                if len(config_value) == 0:
                    raise InvalidConfigurationError(
                        f"Hmac option '{key}' is empty: '{config_value}'"
                    )

            self._add_hmac = True

    def get_next(self, timeout: float) -> Optional[dict]:
        """Get next document from Kafka.

        Parameters
        ----------
        timeout : float
           Timeout for obtaining a document  from Kafka.

        Returns
        -------
        json_dict : dict
            A document obtained from Kafka.

        Raises
        ------
        CriticalInputError
            Raises if an input is invalid or if it causes an error.

        """
        if self._consumer is None:
            self._create_consumer()

        self._record = self._consumer.poll(timeout=timeout)
        if self._record is None:
            return None

        self.current_offset = self._record.offset()

        if self._record.error():
            raise CriticalInputError(
                f"A confluent-kafka record contains an error code: ({self._record.error()})",
                None,
            )
        try:
            raw_event = self._record.value()
            event_dict = json.loads(raw_event.decode("utf-8"))

            if self._add_hmac:
                hmac_target_field_name = self._config["consumer"]["hmac"]["target"]
                event_dict = self._add_hmac_to(event_dict, hmac_target_field_name, raw_event)

            if isinstance(event_dict, dict):
                return event_dict
            raise InvalidMessageError
        except ValueError as error:
            raise CriticalInputError(
                f"Input record value is not a valid json string: ({self._format_message(error)})",
                self._record.value().decode("utf-8"),
            ) from error
        except InvalidMessageError as error:
            raise CriticalInputError(
                f"Input record value could not be parsed as dict: ({self._format_message(error)})",
                self._record.value().decode("utf-8"),
            ) from error
        except BaseException as error:
            raise CriticalInputError(
                f"Error parsing input record: ({self._format_message(error)})",
                self._record.value().decode("utf-8"),
            ) from error

    def _add_hmac_to(self, event_dict, hmac_target_field_name, raw_event):
        """
        Calculates an HMAC (Hash-based message authentication code) based on a given target field
        and adds it to the given event. If the target field has the value '<RAW_MSG>' the full raw
        byte message is used instead as a target for the HMAC calculation. As a result the target
        field value and the resulting hmac will be added to the original event.
        The target field value will be compressed and base64 encoded though to reduce memory usage.

        Parameters
        ----------
        event_dict: dict
            The event to which the calculated hmac should be appended
        hmac_target_field_name: str
            The dotted field name of the target value that should be used for the hmac calculation.
             If instead '<RAW_MSG>' is used then the hmac will be calculated over the full raw
             event.
        raw_event: bytearray
            The raw event how it is received from kafka.

        Returns
        -------
        event_dict: dict
            The original event extended with a field that has the hmac and the corresponding target
            field, which was
            used to calculate the hmac.
        """

        # calculate hmac of full raw message
        if hmac_target_field_name == "<RAW_MSG>":
            received_orig_message = raw_event
            hmac = HMAC(
                key=self._config["consumer"]["hmac"]["key"].encode(),
                msg=raw_event,
                digestmod=hashlib.sha256,
            ).hexdigest()
        else:
            # calculate hmac of dotted field value
            received_orig_message = get_dotted_field_value(event_dict, hmac_target_field_name)
            if received_orig_message is not None:
                received_orig_message = received_orig_message.encode()
                hmac = HMAC(
                    key=self._config["consumer"]["hmac"]["key"].encode(),
                    msg=received_orig_message,
                    digestmod=hashlib.sha256,
                ).hexdigest()
            else:
                hmac = "error"
                received_orig_message = (
                    f"<expected hmac target field '{hmac_target_field_name}' not found>".encode()
                )
                self.store_failed(
                    f"Couldn't find the hmac target field '{hmac_target_field_name}'",
                    event_dict,
                    event_dict,
                )

        # compress received_orig_message and create output with base 64 encoded
        # compressed received_orig_message
        compressed = compress(received_orig_message, level=-1)
        hmac_output = {"hmac": hmac, "compressed_base64": b64encode(compressed).decode()}

        # add hmac result to the original event
        add_was_successful = add_field_to(
            event_dict, self._config["consumer"]["hmac"]["output_field"], hmac_output
        )
        if not add_was_successful:
            self.store_failed(
                f"Couldn't add the hmac to the input event as the desired output "
                f"field '{self._config['consumer']['hmac']['output_field']}' already exist.",
                event_dict,
                event_dict,
            )
        return event_dict

    @staticmethod
    def _format_message(error: BaseException) -> str:
        return f"{type(error).__name__}: {str(error)}" if str(error) else type(error).__name__

    def store(self, document: dict):
        """Store a document in the producer topic.

        Parameters
        ----------
        document : dict
           Document to store.

        """
        self.store_custom(document, self._producer_topic)

        if not self._enable_auto_offset_store:
            self._consumer.store_offsets(message=self._record)

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
            self._producer.produce(
                target, value=json.dumps(document, separators=(",", ":")).encode("utf-8")
            )
            self._producer.poll(0)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config["producer"]["flush_timeout"])
        except BaseException as error:
            raise CriticalOutputError(
                f"Error storing output document: ({self._format_message(error)})", document
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
                self._producer_error_topic,
                value=json.dumps(value, separators=(",", ":")).encode("utf-8"),
            )
            self._producer.poll(0)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config["producer"]["flush_timeout"])

    def _create_consumer(self):
        self._consumer = Consumer(self._create_confluent_settings())
        self._consumer.subscribe([self._consumer_topic])

    def _create_producer(self):
        self._producer = Producer(self._create_confluent_settings())

    def _create_confluent_settings(self):
        configuration = {
            "bootstrap.servers": ",".join(self._bootstrap_servers),
            "group.id": self._consumer_group,
            "enable.auto.commit": self._config["consumer"]["auto_commit"],
            "session.timeout.ms": self._config["consumer"]["session_timeout"],
            "enable.auto.offset.store": self._enable_auto_offset_store,
            "default.topic.config": {
                "auto.offset.reset": self._config["consumer"]["offset_reset_policy"]
            },
            "acks": self._config["producer"]["ack_policy"],
            "compression.type": self._config["producer"]["compression"],
            "queue.buffering.max.messages": self._config["producer"]["maximum_backlog"],
            "linger.ms": self._config["producer"]["linger_duration"],
        }

        if [self._config["ssl"][key] for key in self._config["ssl"]] != [None, None, None, None]:
            configuration.update(
                {
                    "security.protocol": "SSL",
                    "ssl.ca.location": self._config["ssl"]["cafile"],
                    "ssl.certificate.location": self._config["ssl"]["certfile"],
                    "ssl.key.location": self._config["ssl"]["keyfile"],
                    "ssl.key.password": self._config["ssl"]["password"],
                }
            )

        return configuration

    def shut_down(self):
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None

        if self._producer is not None:
            self._producer.flush(self._config["producer"]["flush_timeout"])
            self._producer = None
