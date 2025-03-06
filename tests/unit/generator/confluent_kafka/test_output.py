# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

from unittest.mock import MagicMock, patch

from logprep.connector.confluent_kafka.output import ConfluentKafkaOutput
from logprep.generator.confluent_kafka.output import ConfluentKafkaGeneratorOutput


class TestConfluentKafkaGeneratorOutput:

    def setup_method(self):
        config = MagicMock()
        self.mock_parent = MagicMock(spec=ConfluentKafkaOutput)
        self.output = ConfluentKafkaGeneratorOutput("test", config)
        self.output.__dict__.update(self.mock_parent.__dict__)
        self.output.store_custom = MagicMock()

    def test_store_calls_store_custom(self):
        self.output.store("test_topic,test_payload")
        self.output.store_custom.assert_called_once_with("test_payload", "test_topic")

    def test_store_handles_empty_payload(self):
        self.output.store("test_topic,")
        self.output.store_custom.assert_called_once_with("", "test_topic")

    def test_store_handles_missing_comma(self):
        self.output.store("test_topic_only")
        self.output.store_custom.assert_called_once_with("", "test_topic_only")

    def test_store_calles_super_store(self):
        with patch.object(ConfluentKafkaOutput, "store", MagicMock()) as mock_store:
            self.output.store({"test_field": "test_value"})
            mock_store.assert_called_once_with({"test_field": "test_value"})
