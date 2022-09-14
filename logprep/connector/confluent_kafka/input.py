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
        bootstrapservers: [127.0.0.1:9092]
        topic: consumer
        group: cgroup
        auto_commit: on
        session_timeout: 6000
        offset_reset_policy: smallest
"""
import json
import sys
from functools import partial
from logging import Logger
from socket import getfqdn
from typing import Any, List, Tuple, Union

from attrs import define, field, validators
from confluent_kafka import Consumer

from logprep.abc.input import CriticalInputError, Input
from logprep.util.validators import dict_with_keys_validator

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property


class ConfluentKafkaInput(Input):
    """A kafka input connector."""

    @define(kw_only=True, slots=False)
    class Config(Input.Config):
        """Kafka specific configurations"""

        bootstrapservers: List[str]
        """This field contains a list of Kafka servers (also known as Kafka brokers or Kafka nodes)
        that can be contacted by Logprep to initiate the connection to a Kafka cluster. The list
        does not have to be complete, since the Kafka server contains contact information for
        other Kafka nodes after the initial connection. It is advised to list at least two Kafka
        servers."""
        topic: str = field(validator=validators.instance_of(str))
        """The topic from which new log messages will be fetched."""
        group: str = field(validator=validators.instance_of(str))
        """Corresponds to the Kafka configuration parameter
        `group.id <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_. The
        individual Logprep processes have the same group.id and thus belong to the same consumer
        group. Thereby partitions of topics can be assigned to individual consumers."""
        enable_auto_offset_store: bool = field(
            validator=validators.instance_of(bool), default=False
        )
        """Corresponds to the Kafka configuration parameter
        `enable.auto.offset.store <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_.
        This parameter defines if the offset is automatically updated in memory by librdkafka.
        Disabling this allows Logprep to update the offset itself more accurately. It is disabled
        per default in Logprep. The default value in librdkafka it is true."""
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
        """In this subsection the settings of TLS/SSL are defined.

        - `cafile` -  Path to a certificate authority (see ssl.ca.location).
        - `certfile` - Path to a file with the certificate of the client 
          (see ssl.certificate.location).
        - `keyfile` - Path to the key file corresponding to the given certificate file 
          (see ssl.key.location).
        - `password` - Password for the given key file (see ssl.key.password).
        """
        auto_commit: bool = field(validator=validators.instance_of(bool), default=True)
        """Corresponds to the Kafka configuration parameter
        `enable.auto.commit <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_.
        Enabling this parameter causes offsets being sent automatically and periodically. The values
        can be either true/false or on/off. Currently, this has to be set to true, since independent
        committing is not implemented in Logprep and it would not make sense to activate it anyways.
        The default setting of librdkafka is true."""
        session_timeout: int = field(validator=validators.instance_of(int), default=6000)
        """Corresponds to the Kafka configuration parameter
        `session.timeout.ms <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_.
        This defines the maximum duration a kafka consumer can be without contact to the Kafka
        broker. The kafka consumer must regularly send a heartbeat to the group coordinator,
        otherwise the consumer will be considered as being unavailable. In this case the group
        coordinator assigns the partition to be processed to another computer while re-balancing.
        The default of librdkafka is 10000 ms (10 s)."""
        offset_reset_policy: str = field(
            default="smallest",
            validator=validators.in_(["latest", "earliest", "none", "largest", "smallest"]),
        )
        """Corresponds to the Kafka configuration parameter
        `auto.offset.reset <https://github.com/edenhill/librdkafka/blob/master/CONFIGURATION.md>`_.
        This parameter influences from which offset the Kafka consumer starts to fetch log messages
        from an assigned partition. The values latest/earliest/none are possible. With a value of
        none Logprep must manage the offset by itself. However, this is not supported by Logprep,
        since it is not relevant for our use-case. If the value is set to latest/largest, the Kafka
        consumer starts by reading the newest log messages of a partition if a valid offset is
        missing. Thus, old log messages from that partition will not be processed. This setting can
        therefore lead to a loss of log messages. A value of earliest/smallest causes the Kafka
        consumer to read all log messages from a partition, which can lead to a duplication of log
        messages. Currently, the deprecated value smallest is used, which should be later changed
        to earliest. The default value of librdkafka is largest."""

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
        consumer = Consumer(self._confluent_settings)
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
        return f"{base_description} - Kafka Input: {self._config.bootstrapservers[0]}"

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
        """Generate confluence settings, mapped from the given kafka logprep configuration.

        Returns
        -------
        configuration : dict
            The confluence kafka settings
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
