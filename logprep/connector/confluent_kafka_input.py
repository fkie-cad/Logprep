"""This module contains functionality that allows to obtain records from kafka."""

from typing import List, Optional
import hashlib
import json
from base64 import b64encode
from hmac import HMAC
from copy import deepcopy
from zlib import compress
from socket import getfqdn
from confluent_kafka import Consumer

from logprep.connector.connector_factory_error import InvalidConfigurationError
from logprep.connector.confluent_kafka_shared import (
    ConfluentKafka,
    ConfluentKafkaFactory,
    UnknownOptionError,
)
from logprep.input.input import Input, CriticalInputError
from logprep.output.output import Output
from logprep.util.helper import add_field_to, get_dotted_field_value


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

    @staticmethod
    def _create_copy_without_base_options(configuration: dict) -> dict:
        config = deepcopy(configuration)
        del config["consumer"]["topic"]
        del config["consumer"]["group"]
        ConfluentKafkaInputFactory._remove_shared_base_options(config)

        return config


class ConfluentKafkaInput(Input, ConfluentKafka):
    """A kafka input connector."""

    def __init__(
        self,
        bootstrap_servers: List[str],
        consumer_topic: str,
        consumer_group: str,
        enable_auto_offset_store: bool,
    ):
        ConfluentKafka.__init__(self, bootstrap_servers)
        self._consumer_topic = consumer_topic
        self._consumer_group = consumer_group
        self._output = None

        self.current_offset = -1

        self._config["consumer"] = {
            "auto_commit": True,
            "session_timeout": 6000,
            "offset_reset_policy": "smallest",
            "enable_auto_offset_store": enable_auto_offset_store,
            "hmac": {"target": "", "key": "", "output_field": ""},
            "preprocessing": {
                "version_info_target_field": "",
                "hmac": {"target": "", "key": "", "output_field": ""},
            },
        }

        self._client_id = getfqdn()
        self._consumer = None
        self._record = None
        self._last_valid_records = {}

        self._add_hmac = False

        self._enable_auto_offset_store = enable_auto_offset_store

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

    def set_option(self, new_options: dict, connector_type: str):
        """Set configuration options for kafka input.

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
        # DEPRECATION: HMAC-Option: Remove this with next major version update, check also the
        # self._config dict in this class's init method
        consumer_options = new_options.get("consumer")
        if consumer_options and "preprocessing" not in consumer_options:
            consumer_options["preprocessing"] = {}
        if new_options.get("consumer", {}).get("hmac"):
            consumer_options["preprocessing"]["hmac"] = new_options["consumer"]["hmac"]

        super().set_option(new_options, connector_type)

        hmac_options = new_options.get("consumer", {}).get("preprocessing", {}).get("hmac", {})
        if hmac_options:
            self._check_for_missing_options(hmac_options)
            self._add_hmac = True

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

    def get_next(self, timeout: float) -> Optional[dict]:
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
        if self._consumer is None:
            self._create_consumer()

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
        raw_event = self._record.value()
        try:
            event_dict = json.loads(raw_event.decode("utf-8"))
        except ValueError as error:
            raise CriticalInputError(
                "Input record value is not a valid json string", raw_event
            ) from error
        if not isinstance(event_dict, dict):
            raise CriticalInputError("Input record value could not be parsed as dict", event_dict)
        if self._add_hmac:
            hmac_target_field_name = (
                self._config.get("consumer", {})
                .get("preprocessing", {})
                .get("hmac", {})
                .get("target")
            )
            event_dict = self._add_hmac_to(event_dict, hmac_target_field_name, raw_event)
        return event_dict

    def _add_hmac_to(self, event_dict, hmac_target_field_name, raw_event):
        """
        Calculates an HMAC (Hash-based message authentication code) based on a given target field
        and adds it to the given event. If the target field has the value '<RAW_MSG>' the full raw
        byte message is used instead as a target for the HMAC calculation. As a result the target
        field value and the resulting hmac will be added to the original event. The target field
        value will be compressed and base64 encoded though to reduce memory usage.

        Parameters
        ----------
        event_dict: dict
            The event to which the calculated hmac should be appended
        hmac_target_field_name: str
            The dotted field name of the target value that should be used for the hmac calculation.
            If instead '<RAW_MSG>' is used then the hmac will be calculated over the full raw event.
        raw_event: bytearray
            The raw event how it is received from kafka.

        Returns
        -------
        event_dict: dict
            The original event extended with a field that has the hmac and the corresponding target
            field, which was used to calculate the hmac.
        """
        hmac_options = self._config.get("consumer", {}).get("preprocessing", {}).get("hmac", {})
        if hmac_target_field_name == "<RAW_MSG>":
            received_orig_message = raw_event
        else:
            received_orig_message = get_dotted_field_value(event_dict, hmac_target_field_name)

        if received_orig_message is None:
            hmac = "error"
            received_orig_message = (
                f"<expected hmac target field '{hmac_target_field_name}' not found>".encode()
            )
            self._output.store_failed(
                f"Couldn't find the hmac target field '{hmac_target_field_name}'",
                event_dict,
                event_dict,
            )
        else:
            if isinstance(received_orig_message, str):
                received_orig_message = received_orig_message.encode("utf-8")
            hmac = HMAC(
                key=hmac_options.get("key").encode(),
                msg=received_orig_message,
                digestmod=hashlib.sha256,
            ).hexdigest()
        compressed = compress(received_orig_message, level=-1)
        hmac_output = {"hmac": hmac, "compressed_base64": b64encode(compressed).decode()}
        add_was_successful = add_field_to(
            event_dict,
            hmac_options.get("output_field"),
            hmac_output,
        )
        if not add_was_successful:
            self._output.store_failed(
                f"Couldn't add the hmac to the input event as the desired output "
                f"field '{hmac_options.get('output_field')}' already exist.",
                event_dict,
                event_dict,
            )
        return event_dict

    def _create_consumer(self):
        self._consumer = Consumer(self._create_confluent_settings())
        self._consumer.subscribe([self._consumer_topic])

    def _create_confluent_settings(self):
        configuration = {
            "group.id": self._consumer_group,
            "enable.auto.commit": self._config["consumer"]["auto_commit"],
            "session.timeout.ms": self._config["consumer"]["session_timeout"],
            "enable.auto.offset.store": self._enable_auto_offset_store,
            "default.topic.config": {
                "auto.offset.reset": self._config["consumer"]["offset_reset_policy"]
            },
        }
        self._set_base_confluent_settings(configuration)

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
