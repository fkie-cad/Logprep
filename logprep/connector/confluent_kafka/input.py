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

    _output: Connector

    current_offset: int

    _record: Any

    _last_valid_records: dict

    __slots__ = [
        "_output",
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
        consumer = Consumer(self._create_confluent_settings())
        consumer.subscribe([self._config.topic])
        return consumer

    def set_option(self, new_options: dict, connector_type: str):
        """Set configuration options for specified kafka connector type.

        Parameters
        ----------
        new_options : dict
           New options to set.
        connector_type : str
           Name of the connector type. Can be either producer or consumer.

        Raises
        ------
        UnknownOptionError
            Raises if an option is invalid.

        """
        default_connector_options = self._config.get(connector_type, {})
        new_connector_options = new_options.get(connector_type, {})
        self._set_connector_type_options(new_connector_options, default_connector_options)

    def _set_connector_type_options(self, user_options, default_options):
        """Iterate recursively over the default options and set the values from the user options."""
        both_options_are_numbers = isinstance(user_options, (int, float)) and isinstance(
            default_options, (int, float)
        )
        options_have_same_type = isinstance(user_options, type(default_options))

        if not options_have_same_type and not both_options_are_numbers:
            raise UnknownOptionError(
                f"Wrong Option type for '{user_options}'. "
                f"Got {type(user_options)}, expected {type(default_options)}."
            )
        if not isinstance(default_options, dict):
            return user_options
        for user_option in user_options:
            if user_option not in default_options:
                raise UnknownOptionError(f"Unknown Option: {user_option}")
            default_options[user_option] = self._set_connector_type_options(
                user_options[user_option], default_options[user_option]
            )
        return default_options

    # def set_ssl_config(self, cafile: str, certfile: str, keyfile: str, password: str):
    #     """Set SSL configuration for kafka.
    #
    #     Parameters
    #     ----------
    #     cafile : str
    #        Path to certificate authority file.
    #     certfile : str
    #        Path to certificate file.
    #     keyfile : str
    #        Path to private key file.
    #     password : str
    #        Password for private key.
    #
    #     """
    #     self._config["ssl"]["cafile"] = cafile
    #     self._config["ssl"]["certfile"] = certfile
    #     self._config["ssl"]["keyfile"] = keyfile
    #     self._config["ssl"]["password"] = password

    @staticmethod
    def _format_error(error: BaseException) -> str:
        return f"{type(error).__name__}: {str(error)}" if str(error) else type(error).__name__

    def _set_base_confluent_settings(self, configuration):
        configuration["bootstrap.servers"] = ",".join(self._bootstrap_servers)
        ssl_settings_are_setted = any(self._config["ssl"][key] for key in self._config["ssl"])
        if ssl_settings_are_setted:
            configuration.update(
                {
                    "security.protocol": "SSL",
                    "ssl.ca.location": self._config["ssl"]["cafile"],
                    "ssl.certificate.location": self._config["ssl"]["certfile"],
                    "ssl.key.location": self._config["ssl"]["keyfile"],
                    "ssl.key.password": self._config["ssl"]["password"],
                }
            )

    def connect_output(self, output_connector: Output):
        """Connect output connector.

        This connector is used to store failed HMACs.

        Parameters
        ----------
        output_connector : Output
           Output connector to connect this input with.
        """
        self._output = output_connector

    def describe_endpoint(self) -> str:
        """Get name of Kafka endpoint with the bootstrap server.

        Returns
        -------
        kafka : ConfluentKafka
            Acts as input and output connector.

        """
        return f"Kafka Input: {self._bootstrap_servers[0]}"

    # def set_option(self, new_options: dict, connector_type: str):
    #     """Set configuration options for kafka input.
    #
    #     Parameters
    #     ----------
    #     new_options : dict
    #        New options to set.
    #     connector_type : str
    #        Name of the connector type. Can be either producer or consumer.
    #
    #     Raises
    #     ------
    #     UnknownOptionError
    #         Raises if an option is invalid.
    #
    #     """
    #     # DEPRECATION: HMAC-Option: Remove this with next major version update, check also the
    #     # self._config dict in this class's init method
    #     consumer_options = new_options.get("consumer")
    #     if consumer_options and "preprocessing" not in consumer_options:
    #         consumer_options["preprocessing"] = {}
    #     if new_options.get("consumer", {}).get("hmac"):
    #         consumer_options["preprocessing"]["hmac"] = new_options["consumer"]["hmac"]
    #
    #     super().set_option(new_options, connector_type)
    #
    #     hmac_options = new_options.get("consumer", {}).get("preprocessing", {}).get("hmac", {})
    #     if hmac_options:
    #         self._check_for_missing_options(hmac_options)
    #         self._add_hmac = True

    def _check_for_missing_options(self, hmac_options):
        valid_hmac_options_keys = set(
            self._config.get("consumer", {}).get("preprocessing", {}).get("hmac", {}).keys()
        )

        missing_options = valid_hmac_options_keys.difference(hmac_options)
        if missing_options:
            raise InvalidConfigurationError(f"Hmac option(s) missing: {missing_options}")

        for option in valid_hmac_options_keys:
            config_value = (
                self._config.get("consumer", {})
                .get("preprocessing", {})
                .get("hmac", {})
                .get(option)
            )
            if len(config_value) == 0:
                raise InvalidConfigurationError(
                    f"Hmac option '{option}' is empty: '{config_value}'"
                )

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

    def _create_confluent_settings(self):
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
        if not self._enable_auto_offset_store:
            if self._last_valid_records:
                for last_valid_records in self._last_valid_records.values():
                    self._consumer.store_offsets(message=last_valid_records)

    def shut_down(self):
        """Close consumer, which also commits kafka offsets."""
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None
