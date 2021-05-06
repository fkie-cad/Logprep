from copy import deepcopy
from datetime import datetime
from json import loads
from math import isclose
from socket import getfqdn

from pytest import fail, raises

from logprep.connector.confluent_kafka import ConfluentKafka, ConfluentKafkaFactory, UnknownOptionError
from logprep.connector.connector_factory import InvalidConfigurationError
from logprep.input.input import CriticalInputError
from logprep.output.output import CriticalOutputError


class TestConfluentKafkaFactory:
    valid_configuration = {
        'type': 'confluentkafka',
        'bootstrapservers': ['testserver:9092'],
        'consumer': {
            'topic': 'test_input_raw',
            'group': 'test_consumergroup',
            'auto_commit': False,
            'session_timeout': 654321,
            'offset_reset_policy': 'latest',
        },
        'producer': {
            'topic': 'test_input_processed',
            'error_topic': 'test_error_producer',
            'ack_policy': '1',
            'compression': 'gzip',
            'maximum_backlog': 987654,
            'send_timeout': 2,
            'flush_timeout': 30,
            'linger_duration': 4321,
        },
        'ssl': {
            'cafile': 'test_cafile',
            'certfile': 'test_certfile',
            'keyfile': 'test_keyfile',
            'password': 'test_password'
        }
    }

    def setup_method(self, method_name):
        self.config = deepcopy(self.valid_configuration)

    def test_fails_if_configuration_is_not_a_dictionary(self):
        for i in ['string', 123, 456.789, None, ConfluentKafkaFactory, ['list'], {'set'}]:
            with raises(InvalidConfigurationError):
                ConfluentKafkaFactory.create_from_configuration(i)

    def test_fails_if_any_base_config_value_is_missing(self):
        configuration = deepcopy(self.valid_configuration)
        del configuration['bootstrapservers']
        with raises(InvalidConfigurationError):
            ConfluentKafkaFactory.create_from_configuration(configuration)

        for i in ['topic', 'group']:
            configuration = deepcopy(self.valid_configuration)
            del configuration['consumer'][i]

            with raises(InvalidConfigurationError):
                ConfluentKafkaFactory.create_from_configuration(configuration)

        configuration = deepcopy(self.valid_configuration)
        del configuration['producer']['topic']

        with raises(InvalidConfigurationError):
            ConfluentKafkaFactory.create_from_configuration(configuration)

    def test_ssl_config_values_are_none_if_section_is_missing(self):
        del self.config['ssl']
        kafka = ConfluentKafkaFactory.create_from_configuration(self.config)

        assert [kafka._config['ssl'][key] for key in kafka._config['ssl']] == [None for i in
                                                                               range(4)]

    def test_ssl_config_values_are_set_if_section_ssl_section_is_present(self):
        kafka = ConfluentKafkaFactory.create_from_configuration(self.config)

        assert kafka._config['ssl']['cafile'] == self.config['ssl']['cafile']
        assert kafka._config['ssl']['certfile'] == self.config['ssl']['certfile']
        assert kafka._config['ssl']['keyfile'] == self.config['ssl']['keyfile']
        assert kafka._config['ssl']['password'] == self.config['ssl']['password']

    def test_various_options_are_set_from_configuration(self):
        kafka = ConfluentKafkaFactory.create_from_configuration(self.config)

        assert kafka._config['consumer']['auto_commit'] == False
        assert kafka._config['consumer']['session_timeout'] == self.config['consumer'][
            'session_timeout']
        assert kafka._config['consumer']['offset_reset_policy'] == self.config['consumer'][
            'offset_reset_policy']

        assert kafka._config['producer']['ack_policy'] == self.config['producer']['ack_policy']
        assert kafka._config['producer']['compression'] == self.config['producer']['compression']
        assert kafka._config['producer']['flush_timeout'] == self.config['producer'][
            'flush_timeout']
        assert kafka._config['producer']['linger_duration'] == self.config['producer'][
            'linger_duration']
        assert kafka._config['producer']['maximum_backlog'] == self.config['producer'][
            'maximum_backlog']
        assert kafka._config['producer']['send_timeout'] == self.config['producer']['send_timeout']


class NotJsonSerializableMock:
    pass


class ProducerMock:
    def __init__(self):
        self.produced = []

    def produce(self, topic, value):
        self.produced.append((topic, loads(value.decode())))

    def poll(self, timeout):
        pass

    def flush(self, timeout):
        pass


class ConfluentKafkaForTest(ConfluentKafka):
    def _create_producer(self):
        self._producer = ProducerMock()


class RecordMock:
    def __init__(self, record_value, record_error):
        self.record_value = record_value
        self.record_error = record_error

    def value(self):
        if self.record_value is None:
            return None
        else:
            return self.record_value.encode("utf-8")

    def error(self):
        if self.record_error is None:
            return None
        else:
            return self.record_error

    def offset(self):
        return -1


class ConsumerInvalidJsonMock:
    def poll(self, timeout):
        return RecordMock('This is not a valid JSON string!', None)


class ConsumerRecordWithKafkaErrorMock:
    def poll(self, timeout):
        return RecordMock('{"test_variable" : "test value" }',
                          'An arbitrary confluent-kafka error')


class ConsumerNoRecordMock:
    def poll(self, timeout):
        return None


class TestConfluentKafka:
    default_configuration = {
        'bootstrap.servers': 'bootstrap1,bootstrap2',
        'group.id': 'consumer_group',
        'enable.auto.commit': True,
        'session.timeout.ms': 6000,
        'default.topic.config': {'auto.offset.reset': 'smallest'},
        'acks': 'all',
        'compression.type': 'none',
        'queue.buffering.max.messages': 31337,
        'linger.ms': 0
    }

    def setup_method(self, _):
        self.config = deepcopy(self.default_configuration)
        self.kafka = ConfluentKafka(['bootstrap1', 'bootstrap2'],
                                    'consumer_topic',
                                    'consumer_group',
                                    'producer_topic',
                                    'producer_error_topic')

    def remove_options(self, *args):
        for key in args:
            del self.config[key]

    def test_implements_abstract_methods(self):
        try:
            ConfluentKafka(['127.0.0.1:27001'], 'consumertopic', 'consumergroup', 'producertopic',
                           'producer_error_topic')
        except TypeError as err:
            fail('Must implement abstract methods: %s' % str(err))

    def test_describe_endpoint_returns_kafka_with_first_boostrap_config(self):
        assert self.kafka.describe_endpoint() == 'Kafka: bootstrap1'

    def test_client_id_is_set_to_hostname(self):
        assert self.kafka._client_id == getfqdn()

    def test_set_option_fails_for_unknown_and_construction_options(self):
        for i in ['unknown', 'no_such_option',
                  'consumer_no_such_option', 'consumer_group', 'consumer_topic',
                  'producer_option', 'producer_topic', 'producer_error_topic']:
            with raises(UnknownOptionError):
                self.kafka.set_option({i: True})

    def test_set_option_accepts_known_non_constructor_non_ssl_options(self):
        consumer_options = [{'consumer': {'auto_commit': True}},
                            {'consumer': {'session_timeout': 0}},
                            {'consumer': {'offset_reset_policy': 'smallest'}}]
        producer_options = [{'producer': {'send_timeout': 0}},
                            {'producer': {'flush_timeout': 30.0}},
                            {'producer': {'linger_duration': 0}},
                            {'producer': {'maximum_backlog': 10 * 1000}},
                            {'producer': {'compression': 'none'}},
                            {'producer': {'ack_policy': 'all'}}]
        try:
            for i in consumer_options + producer_options:
                self.kafka.set_option(i)
        except UnknownOptionError:
            fail('set_option should allow setting non-constructor and non-ssl options.')

    def test_create_confluent_settings_returns_expected_dict_without_ssl(self):
        self.kafka.set_option({'producer': {'maximum_backlog': 31337}})

        assert self.kafka._create_confluent_settings() == self.config

    def test_create_confluent_settings_returns_expected_dict_with_ssl(self):
        self.kafka.set_option({'producer': {'maximum_backlog': 42}})
        self.kafka.set_ssl_config('cafile', 'certificatefile', 'keyfile', 'password')

        self.config.update({
            'queue.buffering.max.messages': 42,
            'security.protocol': 'SSL',
            'ssl.ca.location': 'cafile',
            'ssl.certificate.location': 'certificatefile',
            'ssl.key.location': 'keyfile',
            'ssl.key.password': 'password'
        })

        assert self.kafka._create_confluent_settings() == self.config

    def test_create_confluent_settings_contains_expected_values(self):
        options = {
            'consumer': {
                'auto_commit': False,
                'session_timeout': 23456,
                'offset_reset_policy': 'latest'
            },
            'producer': {
                'ack_policy': '1',
                'compression': 'gzip',
                'maximum_backlog': 4711,
                'linger_duration': 12345
            }
        }

        self.config['enable.auto.commit'] = False
        self.config['session.timeout.ms'] = 23456
        self.config['default.topic.config']['auto.offset.reset'] = 'latest'
        self.config['acks'] = '1'
        self.config['compression.type'] = 'gzip'
        self.config['queue.buffering.max.messages'] = 4711
        self.config['linger.ms'] = 12345

        self.kafka.set_option(options)

        assert self.kafka._create_confluent_settings() == self.config

    def test_store_sends_event_to_expected_topic(self):
        producer_topic = 'producer_topic'
        event = {'field': 'content'}
        expected = (producer_topic, event)

        kafka = ConfluentKafkaForTest(['bootstrap1', 'bootstrap2'],
                                      'consumer_topic',
                                      'consumer_group',
                                      producer_topic,
                                      'producer_error_topic')
        kafka.store(event)

        assert len(kafka._producer.produced) == 1
        assert kafka._producer.produced[0] == expected

    def test_store_custom_sends_event_to_expected_topic(self):
        custom_topic = 'custom_topic'
        event = {'field': 'content'}
        expected = (custom_topic, event)

        kafka = ConfluentKafkaForTest(['bootstrap1', 'bootstrap2'],
                                      'consumer_topic',
                                      'consumer_group',
                                      'default_topic',
                                      'producer_error_topic')
        kafka.store_custom(event, custom_topic)

        assert len(kafka._producer.produced) == 1
        assert kafka._producer.produced[0] == expected

    def test_store_failed(self):
        producer_error_topic = 'producer_error_topic'
        event_received = {'field': 'received'}
        event = {'field': 'content'}
        error_message = 'error message'

        expected = (producer_error_topic, {'error': error_message,
                                           'original': event_received,
                                           'processed': event,
                                           'timestamp': str(datetime.now())})

        kafka = ConfluentKafkaForTest(['bootstrap1', 'bootstrap2'],
                                      'consumer_topic',
                                      'consumer_group',
                                      'producer_topic',
                                      producer_error_topic)
        kafka.store_failed(error_message, event_received, event)

        assert len(kafka._producer.produced) == 1

        error_topic = kafka._producer.produced[0]

        # timestamp is compared to be approximately the same,
        # since it is variable and then removed to compare the rest
        date_format = '%Y-%m-%d %H:%M:%S.%f'
        error_time = datetime.timestamp(datetime.strptime(error_topic[1]['timestamp'], date_format))
        expected_time = datetime.timestamp(datetime.strptime(expected[1]['timestamp'], date_format))
        assert isclose(error_time, expected_time)
        del error_topic[1]['timestamp']
        del expected[1]['timestamp']

        assert error_topic == expected

    def test_get_next_returns_none_if_no_records(self):
        kafka = ConfluentKafkaForTest(['bootstrap1', 'bootstrap2'],
                                      'consumer_topic',
                                      'consumer_group',
                                      'producer_topic',
                                      'producer_error_topic')

        kafka._consumer = ConsumerNoRecordMock()

        assert kafka.get_next(1) is None

    def test_get_next_raises_critical_input_exception_for_invalid_confluent_kafka_record(self):
        kafka = ConfluentKafkaForTest(['bootstrap1', 'bootstrap2'],
                                      'consumer_topic',
                                      'consumer_group',
                                      'producer_topic',
                                      'producer_error_topic')

        kafka._consumer = ConsumerRecordWithKafkaErrorMock()

        with raises(CriticalInputError,
                    match=r'A confluent-kafka record contains an error code: '
                          r'\(An arbitrary confluent-kafka error\)'):
            kafka.get_next(1)

    def test_get_next_raises_critical_input_exception_for_invalid_json_string(self):
        kafka = ConfluentKafkaForTest(['bootstrap1', 'bootstrap2'],
                                      'consumer_topic',
                                      'consumer_group',
                                      'producer_topic',
                                      'producer_error_topic')

        kafka._consumer = ConsumerInvalidJsonMock()

        with raises(CriticalInputError,
                    match=r'Input record value is not a valid json string: '
                          r'\(JSONDecodeError\: Expecting value\: line 1 column 1 \(char 0\)\)'):
            kafka.get_next(1)

    def test_create_confluent_settings_contains_expected_values2(self):
        with raises(CriticalOutputError,
                    match=r'Error storing output document: \(TypeError: Object of type '
                          r'\'NotJsonSerializableMock\' is not JSON serializable\)'):
            self.kafka.store({'invalid_json': NotJsonSerializableMock(), 'something_valid': 'im_valid!'})
            