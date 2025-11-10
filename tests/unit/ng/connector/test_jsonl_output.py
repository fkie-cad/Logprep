# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
# pylint: disable=line-too-long

import copy
import tempfile
from unittest import mock

from logprep.connector.jsonl.output import JsonlOutput
from logprep.factory import Factory
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.connector.base import BaseOutputTestCase


class TestJsonlOutputOutput(BaseOutputTestCase):
    CONFIG = {
        "type": "ng_jsonl_output",
        "output_file": f"{tempfile.gettempdir()}/output.jsonl",
        "output_file_custom": f"{tempfile.gettempdir()}/custom_file",
    }

    def setup_method(self) -> None:
        super().setup_method()
        self.event = LogEvent({"message": "test message"}, original=b"")

    def test_store_appends_document_to_variable(self):
        self.object.store(self.event)
        assert len(self.object.events) == 1
        assert self.object.events[0] == self.event.data

    def test_store_custom_appends_document_to_variable(self):
        self.object.store_custom(self.event, target="whatever")
        assert len(self.object.events) == 1
        assert self.object.events[0] == {"whatever": self.event.data}

    def test_store_maintains_order_of_documents(self):
        for i in range(0, 3):
            self.object.store(LogEvent({"order": i}, original=b""))

        assert len(self.object.events) == 3
        for order in range(0, 3):
            assert self.object.events[order]["order"] == order

    @mock.patch("logprep.ng.connector.jsonl.output.JsonlOutput._write_json")
    def test_write_document_to_file_on_store(self, _):
        self.object.store(self.event)
        self.object._write_json.assert_called_with(self.CONFIG["output_file"], self.event.data)

    @mock.patch("logprep.ng.connector.jsonl.output.JsonlOutput._write_json")
    def test_write_document_to_file_on_store_custom(self, _):
        self.object.store_custom(self.event, target="whatever")
        self.object._write_json.assert_called_with(
            self.CONFIG["output_file_custom"], {"whatever": self.event.data}
        )

    @mock.patch("logprep.ng.connector.jsonl.output.JsonlOutput._write_json")
    def test_write_multiple_documents_to_file_on_store(self, _):
        self.object.store(LogEvent(self.event.data, original=b""))
        self.object.store(LogEvent(self.event.data, original=b""))
        assert self.object._write_json.call_count == 2
        assert self.object._write_json.call_args_list == [
            mock.call(self.CONFIG["output_file"], {"message": "test message"}),
            mock.call(self.CONFIG["output_file"], {"message": "test message"}),
        ]

    @mock.patch("builtins.open")
    def test_write_json_writes_to_file(self, mock_open):
        JsonlOutput._write_json("the/file/path", self.event.data)
        mock_open.assert_called_with("the/file/path", "a+", encoding="utf8")

    @mock.patch("builtins.open")
    def test_setup_creates_single_file_if_only_output_file(self, mock_open):
        config = copy.deepcopy(self.CONFIG)
        config["output_file_custom"] = ""
        self.object = Factory.create({"Test Instance Name": config})
        self.object.setup()
        mock_open.assert_called()
        assert mock_open.call_count == 1

    @mock.patch("builtins.open")
    def test_store_counts_processed_events(self, _):  # pylint: disable=arguments-differ
        self.object.metrics.number_of_processed_events = 0
        self.object.store(LogEvent({"message": "my event message"}, original=b""))
        assert self.object.metrics.number_of_processed_events == 1

    @mock.patch("builtins.open")
    def test_store_calls_batch_finished_callback_without_errors(
        self, _
    ):  # pylint: disable=arguments-differ
        self.object.input_connector = mock.MagicMock()
        self.object.store(LogEvent({"message": "my event message"}, original=b""))

    def test_store_handles_errors(self):
        """you have to override this method in some output implementations depending on the implementation of the store and write_backlog methods."""
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        with mock.patch(
            "logprep.ng.connector.jsonl.output.JsonlOutput._write_json",
            side_effect=Exception("Test error"),
        ):
            self.object.store(event)
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

    def test_store_custom_handles_errors(self):
        """you have to override this method in some output implementations depending on the implementation of the store and write_backlog methods."""
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        with mock.patch(
            "logprep.ng.connector.jsonl.output.JsonlOutput._write_json",
            side_effect=Exception("Test error"),
        ):
            self.object.store_custom(event, target="custom_target")
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED, f"{event.state} should be FAILED"

    def test_store_handles_errors_failed_event(self):
        """you have to override this method in some output implementations depending on the implementation of the store and write_backlog methods."""
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.FAILED)
        with mock.patch(
            "logprep.ng.connector.jsonl.output.JsonlOutput._write_json",
            side_effect=Exception("Test error"),
        ):
            self.object.store(event)
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

    def test_store_custom_handles_errors_failed_event(self):
        """you have to override this method in some output implementations depending on the implementation of the store and write_backlog methods."""
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.FAILED)
        with mock.patch(
            "logprep.ng.connector.jsonl.output.JsonlOutput._write_json",
            side_effect=Exception("Test error"),
        ):
            self.object.store_custom(event, target="custom_target")
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED, f"{event.state} should be FAILED"
