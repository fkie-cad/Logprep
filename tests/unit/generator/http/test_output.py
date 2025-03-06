# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

from unittest.mock import MagicMock

from logprep.generator.http.output import HttpGeneratorOutput


class TestConfluentKafkaGeneratorOutput:

    def setup_method(self):
        mock_config = MagicMock()
        mock_config.target_url = "test_url.com/"
        self.output = HttpGeneratorOutput("test", mock_config)
        self.output.store_custom = MagicMock()  # Mock the store_custom method

    def test_store_calls_store_custom(self):
        self.output.store("test_path,test_payload")
        self.output.store_custom.assert_called_once_with("test_payload", "test_url.com/test_path")

    def test_store_handles_empty_payload(self):
        self.output.store("test_path,")
        self.output.store_custom.assert_called_once_with("", "test_url.com/test_path")

    def test_store_handles_missing_comma(self):
        self.output.store("test_path")
        self.output.store_custom.assert_called_once_with("", "test_url.com/test_path")
