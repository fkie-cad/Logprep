"""This module contains functionality that allows to establish a connection with kafka."""

from typing import List, Optional
from copy import deepcopy
from datetime import datetime
from json import dumps, loads, JSONDecodeError
from socket import getfqdn

from confluent_kafka import Consumer, Producer

from logprep.connector.connector_factory_error import InvalidConfigurationError
from logprep.input.input import Input, CriticalInputError
from logprep.output.output import Output, CriticalOutputError


class ConfluentKafkaError(BaseException):
    """Base class for ConfluentKafka related exceptions."""


class UnknownOptionError(ConfluentKafkaError):
    """Raise if an invalid option has been set in the ConfluentKafka configuration."""


class InvalidMessageError(ConfluentKafkaError):
    """Raise if an invalid message has been received by ConfluentKafka."""


class ConfluentKafkaFactory:
    """Create ConfluentKafka connectors for logprep and input/output communication."""

    @staticmethod
    def create_from_configuration(configuration: dict) -> 'ConfluentKafka':
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
        InvalidConfigurationError
            If ConfluentKafka configuration is invalid.

        """
        if not isinstance(configuration, dict):
            raise InvalidConfigurationError

        try:
            kafka = ConfluentKafka(configuration['bootstrapservers'],
                                   configuration['consumer']['topic'],
                                   configuration['consumer']['group'],
                                   configuration['producer']['topic'],
                                   configuration['producer']['error_topic'])
        except KeyError:
            raise InvalidConfigurationError

        if 'ssl' in configuration:
            ConfluentKafkaFactory._set_ssl_options(kafka, configuration['ssl'])

        configuration = ConfluentKafkaFactory._create_copy_without_base_options(configuration)

        try:
            kafka.set_option(configuration)
        except UnknownOptionError as error:
            raise InvalidConfigurationError('Confluent Kafka: ' + str(error))

        return kafka

    @staticmethod
    def _set_ssl_options(kafka: 'ConfluentKafka', ssl_config: dict):
        ssl_keys = ['cafile', 'certfile', 'keyfile', 'password']
        if not any([i in ssl_config for i in ssl_keys]):
            return

        cafile = ssl_config['cafile'] if 'cafile' in ssl_config else None
        certfile = ssl_config['certfile'] if 'certfile' in ssl_config else None
        keyfile = ssl_config['keyfile'] if 'keyfile' in ssl_config else None
        password = ssl_config['password'] if 'password' in ssl_config else None

        kafka.set_ssl_config(cafile, certfile, keyfile, password)

    @staticmethod
    def _create_copy_without_base_options(configuration: dict) -> dict:
        config = deepcopy(configuration)
        del config['type']
        del config['bootstrapservers']
        del config['consumer']['topic']
        del config['consumer']['group']
        del config['producer']['topic']
        del config['producer']['error_topic']

        if 'ssl' in config:
            del config['ssl']

        return config

    @staticmethod
    def _set_if_exists(key: str, config: dict, kafka_setter):
        if key in config:
            kafka_setter(config[key])


class ConfluentKafka(Input, Output):
    """A kafka connector that serves as both input and output connector."""

    def __init__(self, bootstrap_servers: List[str], consumer_topic: str, consumer_group: str, producer_topic: str,
                 producer_error_topic: str):
        self._bootstrap_servers = bootstrap_servers
        self._consumer_topic = consumer_topic
        self._consumer_group = consumer_group
        self._producer_topic = producer_topic
        self._producer_error_topic = producer_error_topic

        self.current_offset = -1

        self._config = {
            'ssl': {
                'cafile': None,
                'certfile': None,
                'keyfile': None,
                'password': None
            },
            'consumer': {
                'auto_commit': True,
                'session_timeout': 6000,
                'offset_reset_policy': 'smallest'
            },
            'producer': {
                'ack_policy': 'all',
                'compression': 'none',
                'maximum_backlog': 10 * 1000,
                'linger_duration': 0,
                'send_timeout': 0,
                'flush_timeout': 30.0  # may require adjustment
            }
        }

        self._flush_timeout = 0.01  # may require adjustment

        self._client_id = getfqdn()
        self._consumer = None
        self._producer = None

    def describe_endpoint(self) -> str:
        """Get name of Kafka endpoint with the bootstrap server.

        Returns
        -------
        kafka : ConfluentKafka
            Acts as input and output connector.

        """
        return 'Kafka: ' + str(self._bootstrap_servers[0])

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
        self._config['ssl']['cafile'] = cafile
        self._config['ssl']['certfile'] = certfile
        self._config['ssl']['keyfile'] = keyfile
        self._config['ssl']['password'] = password

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
        for key in new_options:
            if key not in self._config:
                raise UnknownOptionError(f'Unknown Option: {key}')
            if isinstance(new_options[key], dict):
                for subkey in new_options[key]:
                    if subkey not in self._config[key]:
                        raise UnknownOptionError(f'Unknown Option: {key}/{subkey}')
                    self._config[key][subkey] = new_options[key][subkey]

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

        record = self._consumer.poll(timeout=timeout)
        if record is None:
            return None

        self.current_offset = record.offset()

        if record.error():
            raise CriticalInputError('A confluent-kafka record contains an error code: '
                                     '({})'.format(record.error()), None)
        try:
            json_dict = loads(record.value().decode("utf-8"))
            if isinstance(json_dict, dict):
                return json_dict
            raise InvalidMessageError
        except JSONDecodeError as error:
            raise CriticalInputError('Input record value is not a valid json string: '
                                     '({})'.format(self._format_message(error)),
                                     record.value().decode("utf-8")) from error
        except InvalidMessageError as error:
            raise CriticalInputError('Input record value could not be parsed '
                                     'as dict: ({})'.format(self._format_message(error)),
                                     record.value().decode("utf-8")) from error
        except BaseException as error:
            raise CriticalInputError('Error parsing input record: ({})'.format(
                self._format_message(error)), record.value().decode("utf-8")) from error

    @staticmethod
    def _format_message(error: BaseException) -> str:
        return '{}: {}'.format(type(error).__name__,
                               str(error)) if str(error) else type(error).__name__

    def store(self, document: dict):
        """Store a document in the producer topic.

        Parameters
        ----------
        document : dict
           Document to store.

        """
        self.store_custom(document, self._producer_topic)

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
            self._producer.produce(target, value=dumps(document).encode('utf-8'))
            self._producer.poll(0)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config['producer']['flush_timeout'])
        except BaseException as error:
            raise CriticalOutputError('Error storing output document: ({})'.format(
                self._format_message(error)), document) from error

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
            'error': error_message,
            'original': document_received,
            'processed': document_processed,
            'timestamp': str(datetime.now())
        }
        try:
            self._producer.produce(self._producer_error_topic, value=dumps(value).encode('utf-8'))
            self._producer.poll(0)
        except BufferError:
            # block program until buffer is empty
            self._producer.flush(timeout=self._config['producer']['flush_timeout'])

    def _create_consumer(self):
        self._consumer = Consumer(self._create_confluent_settings())
        self._consumer.subscribe([self._consumer_topic])

    def _create_producer(self):
        self._producer = Producer(self._create_confluent_settings())

    def _create_confluent_settings(self):
        configuration = {
            'bootstrap.servers': ','.join(self._bootstrap_servers),
            'group.id': self._consumer_group,
            'enable.auto.commit': self._config['consumer']['auto_commit'],
            'session.timeout.ms': self._config['consumer']['session_timeout'],
            'default.topic.config': {'auto.offset.reset':
                                        self._config['consumer']['offset_reset_policy']},
            'acks': self._config['producer']['ack_policy'],
            'compression.type': self._config['producer']['compression'],
            'queue.buffering.max.messages': self._config['producer']['maximum_backlog'],
            'linger.ms': self._config['producer']['linger_duration']
        }

        if [self._config['ssl'][key] for key in self._config['ssl']] != [None, None, None, None]:
            configuration.update({
                'security.protocol': 'SSL',
                'ssl.ca.location': self._config['ssl']['cafile'],
                'ssl.certificate.location': self._config['ssl']['certfile'],
                'ssl.key.location': self._config['ssl']['keyfile'],
                'ssl.key.password': self._config['ssl']['password']
            })

        return configuration

    def shut_down(self):
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None

        if self._producer is not None:
            self._producer.flush(self._config['producer']['flush_timeout'])
            self._producer = None
