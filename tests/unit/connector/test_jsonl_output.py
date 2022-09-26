# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
from unittest import mock
from logprep.connector.jsonl.output import JsonlOutput
from tests.unit.connector.base import BaseOutputTestCase


class TestJsonlOutputOutput(BaseOutputTestCase):
    CONFIG = {
        "type": "jsonl_output",
        "output_file": "does/not/matter",
        "output_file_custom": "custom_file",
        "output_file_error": "error_file",
    }

    def setup_method(self) -> None:
        super().setup_method()
        self.document = {"message": "test message"}

    @mock.patch("logprep.connector.jsonl.output.JsonlOutput._write_json")
    def test_store_appends_document_to_variable(self, _):
        self.object.store(self.document)
        assert len(self.object.events) == 1
        assert self.object.events[0] == self.document

    @mock.patch("logprep.connector.jsonl.output.JsonlOutput._write_json")
    def test_store_custom_appends_document_to_variable(self, _):
        self.object.store_custom(self.document, target="whatever")
        assert len(self.object.events) == 1
        assert self.object.events[0] == {"whatever": self.document}

    @mock.patch("logprep.connector.jsonl.output.JsonlOutput._write_json")
    def test_store_maintains_order_of_documents(self, _):
        for i in range(0, 3):
            self.object.store({"order": i})

        assert len(self.object.events) == 3
        for order in range(0, 3):
            assert self.object.events[order]["order"] == order

    @mock.patch("logprep.connector.jsonl.output.JsonlOutput._write_json")
    def test_stores_failed_events_in_respective_list(self, _):
        self.object.store_failed("message", {"doc": "received"}, {"doc": "processed"})
        assert len(self.object.failed_events) == 1
        assert self.object.failed_events[0] == (
            "message",
            {"doc": "received"},
            {"doc": "processed"},
        )

    @mock.patch("logprep.connector.jsonl.output.JsonlOutput._write_json")
    def test_write_document_to_file_on_store(self, _):
        self.object.store(self.document)
        self.object._write_json.assert_called_with("does/not/matter", self.document)

    @mock.patch("logprep.connector.jsonl.output.JsonlOutput._write_json")
    def test_write_document_to_file_on_store_custom(self, _):
        self.object.store_custom(self.document, target="whatever")
        self.object._write_json.assert_called_with(
            self.object._config.output_file_custom, {"whatever": self.document}
        )

    @mock.patch("logprep.connector.jsonl.output.JsonlOutput._write_json")
    def test_write_multiple_documents_to_file_on_store(self, _):
        self.object.store(self.document)
        self.object.store(self.document)
        assert self.object._write_json.call_count == 2
        assert self.object._write_json.call_args_list == [
            mock.call("does/not/matter", {"message": "test message"}),
            mock.call("does/not/matter", {"message": "test message"}),
        ]

    @mock.patch("logprep.connector.jsonl.output.JsonlOutput._write_json")
    def test_store_failed_writes_errors(self, _):
        self.object.store_failed("my error message", self.document, self.document)
        self.object._write_json.assert_called_with(
            "error_file",
            {
                "error_message": "my error message",
                "document_received": {"message": "test message"},
                "document_processed": {"message": "test message"},
            },
        )

    @mock.patch("builtins.open")
    def test_write_json_writes_to_file(self, mock_open):
        JsonlOutput._write_json("the/file/path", self.document)
        mock_open.assert_called_with("the/file/path", "a+", encoding="utf8")

    @mock.patch("builtins.open")
    def test_setup_creates_single_file_if_only_output_file(self, mock_open):
        self.object._config.output_file_custom = ""
        self.object._config.output_file_error = ""
        self.object.setup()
        mock_open.assert_called()
        assert mock_open.call_count == 1

    @mock.patch("builtins.open")
    def test_store_counts_processed_events(self, _):  # pylint: disable=arguments-differ
        assert self.object.metrics.number_of_processed_events == 0
        self.object.store({"message": "my event message"})
        assert self.object.metrics.number_of_processed_events == 1

    @mock.patch("builtins.open")
    def test_store_calls_batch_finished_callback(self, _):  # pylint: disable=arguments-differ
        self.object.input_connector = mock.MagicMock()
        self.object.store({"message": "my event message"})
        self.object.input_connector.batch_finished_callback.assert_called()

    @mock.patch("builtins.open")
    def test_store_calls_batch_finished_callback_without_errors(
        self, _
    ):  # pylint: disable=arguments-differ
        self.object.input_connector = mock.MagicMock()
        self.object.store({"message": "my event message"})
