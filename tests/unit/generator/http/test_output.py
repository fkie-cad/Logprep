# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

from unittest.mock import MagicMock, patch

from logprep.connector.http.output import HttpOutput
from logprep.generator.http.output import HttpGeneratorOutput


class TestConfluentKafkaGeneratorOutput:

    def setup_method(self):
        mock_config = MagicMock()
        mock_config.target_url = "test_url.com/"
        self.mock_parent = MagicMock(spec=HttpOutput)
        self.output = HttpGeneratorOutput("test", mock_config)
        self.output.__dict__.update(self.mock_parent.__dict__)
        self.output.store_custom = MagicMock()  # Mock the store_custom method

    def test_store_calles_super_store(self):
        with patch.object(HttpOutput, "store", MagicMock()) as mock_store:
            self.output.store({"test_field": "test_value"})
            mock_store.assert_called_once_with({"test_field": "test_value"})

    def test_store_calls_store_custom(self):
        self.output.store("test_path,test_payload")
        self.output.store_custom.assert_called_once_with("test_payload", "test_url.com/test_path")

    def test_store_handles_empty_payload(self):
        self.output.store("test_path,")
        self.output.store_custom.assert_called_once_with("", "test_url.com/test_path")

    def test_store_handles_missing_comma(self):
        self.output.store("test_path")
        self.output.store_custom.assert_called_once_with("", "test_url.com/test_path")
