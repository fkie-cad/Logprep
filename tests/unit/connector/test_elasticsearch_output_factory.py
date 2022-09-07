# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
from copy import deepcopy

from pytest import fail, raises

from logprep.connector.elasticsearch.output import ElasticsearchOutputFactory
from logprep.pipeline_component_factory import InvalidConfigurationError

# '

# class TestElasticsearchFactory:
#     valid_configuration = {
#         "type": "confluentkafka",
#         "bootstrapservers": ["testserver:9092"],
#         "consumer": {
#             "topic": "test_input_raw",
#             "group": "test_consumergroup",
#             "auto_commit": False,
#             "session_timeout": 654321,
#             "enable_auto_offset_store": True,
#             "offset_reset_policy": "latest",
#         },
#         "elasticsearch": {
#             "hosts": "127.0.0.1:9200",
#             "default_index": "default_index",
#             "error_index": "error_index",
#             "message_backlog": 5,
#             "timeout": 300,
#         },
#     }

#     def setup_method(self, _):
#         config = deepcopy(self.valid_configuration)
#         self.kafka_input = ConfluentKafkaInputFactory.create_from_configuration(config)

#     def test_es_output_creation(self):
#         ElasticsearchOutputFactory.create_from_configuration(self.valid_configuration)

#     def test_fails_if_configuration_is_not_a_dictionary(self):
#         for i in ["string", 123, 456.789, None, ElasticsearchOutputFactory, ["list"], {"set"}]:
#             with raises(InvalidConfigurationError):
#                 ElasticsearchOutputFactory.create_from_configuration(i)

#     def test_fails_if_any_base_config_value_is_missing_for_output(self):
#         for i in ["hosts", "default_index", "error_index", "message_backlog"]:
#             config = deepcopy(self.valid_configuration)
#             del config["elasticsearch"][i]
#             with raises(InvalidConfigurationError):
#                 ElasticsearchOutputFactory.create_from_configuration(config)

#         for i in ["timeout"]:
#             config = deepcopy(self.valid_configuration)
#             del config["elasticsearch"][i]
#             try:
#                 ElasticsearchOutputFactory.create_from_configuration(config)
#             except InvalidConfigurationError:
#                 fail(f"Missing config parameter: {i}")
