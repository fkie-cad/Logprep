# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
from unittest import mock
from logprep.connector.jsonl.output import JsonlOutput


@mock.patch("builtins.open")
class TestJsonlOutputOutput:
    def setup_method(self):
        self.original_write_json = JsonlOutput._write_json
        self.document = {"the": "document"}

    def teardown_method(self):
        JsonlOutput._write_json = self.original_write_json

    def test_describe_endpoint(self, _):
        output = JsonlOutput("doesnotmatter")
        assert output.describe_endpoint() == "writer"

    def test_store_appends_document_to_variable(self, _):
        output = JsonlOutput("doesnotmatter")
        output.store(self.document)
        assert len(output.events) == 1
        assert output.events[0] == self.document

    def test_store_custom_appends_document_to_variable(self, _):
        output = JsonlOutput(output_path="doesnotmatter", output_path_custom="doesnotmatter")
        output.store_custom(self.document, target="whatever")
        assert len(output.events) == 1
        assert output.events[0] == self.document

    def test_store_maintains_order_of_documents(self, _):
        output = JsonlOutput("doesnotmatter")
        for i in range(0, 3):
            output.store({"order": i})

        assert len(output.events) == 3
        for order in range(0, 3):
            assert output.events[order]["order"] == order

    def test_stores_failed_events_in_respective_list(self, _):
        output = JsonlOutput(
            output_path="doesnotmatter",
            output_path_custom="doesnotmatter",
            output_path_error="doesnotmatter",
        )
        output.store_failed("message", {"doc": "received"}, {"doc": "processed"})

        assert len(output.failed_events) == 1
        assert output.failed_events[0] == ("message", {"doc": "received"}, {"doc": "processed"})

    def test_write_document_to_file_on_store(self, mock_open):
        output = JsonlOutput("/file/for/store")
        output.store(self.document)
        mock_open.assert_called_with("/file/for/store", "a+", encoding="utf8")
        mock_open().__enter__().write.assert_called_with('{"the": "document"}\n')

    def test_write_document_to_file_on_store_custom(self, mock_open):
        output = JsonlOutput(output_path="/file/for/store", output_path_custom="/file/for/custom")
        JsonlOutput._write_json = mock.MagicMock()
        output.store_custom(self.document, target="whatever")
        output._write_json.assert_called_with(output._output_file_custom, self.document)

    def test_write_multiple_documents_to_file_on_store(self, mock_open):
        output = JsonlOutput("/file/to/store")
        output.store(self.document)
        output.store(self.document)
        assert mock_open().__enter__().write.call_count == 2
        assert mock_open().__enter__().write.call_args_list == [
            mock.call('{"the": "document"}\n'),
            mock.call('{"the": "document"}\n'),
        ]

    def test_store_failed_writes_errors(self, mock_open):
        output = JsonlOutput(output_path="file/to/store", output_path_error="file/to/error")
        output.store_failed("my error message", self.document, self.document)
        mock_open().__enter__().write.assert_called_with(
            '{"error_message": "my error message", '
            '"document_received": {"the": "document"}, '
            '"document_processed": {"the": "document"}}\n'
        )
