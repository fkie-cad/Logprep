"""This module contains functionality that allows to establish a connection with kafka."""

import json
from datetime import datetime
from functools import cached_property
from socket import getfqdn

from attrs import define
from confluent_kafka import Producer

from logprep.abc.output import Output, CriticalOutputError
from logprep.connector.confluent_kafka.input import ConfluentKafkaInput


class ConfluentKafkaOutput(Output):
    """A kafka connector that serves as output connector."""

    @define(kw_only=True, slots=False)
    class Config(ConfluentKafkaInput.Config):
        """Confluent Kafka Output Config"""

        error_topic: str
        flush_timeout: float

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
        return f"{base_description} - Kafka Output: {self._config.bootstrapservers[0]}"

    def store(self, document: dict) -> None:
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

    def store_custom(self, document: dict, target: str) -> None:
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
            self._producer.flush(timeout=self._config.flush_timeout)
        except BaseException as error:
            raise CriticalOutputError(
                f"Error storing output document: ({error})", document
            ) from error

    def store_failed(
        self, error_message: str, document_received: dict, document_processed: dict
    ) -> None:
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
            self._producer.flush(timeout=self._config.flush_timeout)

    def shut_down(self) -> None:
        """ensures that all messages are flushed"""
        if self._producer is not None:
            self._producer.flush(self._config.flush_timeout)
