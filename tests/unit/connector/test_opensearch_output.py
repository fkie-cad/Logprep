# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
import json
import re
import pytest
from datetime import datetime
from json import loads, dumps
from math import isclose
from unittest import mock

import arrow
import opensearchpy
import opensearchpy.helpers

from logprep.connector.opensearch.output import OpenSearchOutput
from logprep.abc.output import CriticalOutputError, FatalOutputError


class NotJsonSerializableMock:
    pass


def mock_bulk(
    _, documents: list, max_retries: int = 0, chunk_size: int = 500
):  # pylint: disable=unused-argument
    for document in documents:
        try:
            loads(dumps(document))
        except TypeError as error:
            raise CriticalOutputError(
                "Error storing output document: Serialization Error", document
            ) from error


opensearchpy.helpers.bulk = mock_bulk


class TestOpenSearchOutput:
    def setup_method(self, _):
        self.os_output = OpenSearchOutput(
            ["host:123"], "default_index", "error_index", 1, 5000, 0, None, None, None, None
        )

    def test_implements_abstract_methods(self):
        try:
            OpenSearchOutput(
                ["host:123"], "default_index", "error_index", 2, 5000, 0, None, None, None, None
            )
        except TypeError as err:
            pytest.fail(f"Must implement abstract methods: {str(err)}")

    def test_describe_endpoint_returns_opensearch_output(self):
        assert self.os_output.describe_endpoint() == "OpenSearch Output: ['host:123']"

    def test_store_sends_event_to_expected_index_if_index_missing_in_event(self):
        default_index = "target_index"
        event = {"field": "content"}
        expected = {
            "_index": default_index,
            "message": '{"field": "content"}',
            "reason": "Missing index in document",
        }

        os_output = OpenSearchOutput(
            ["host:123"], default_index, "error_index", 1, 5000, 0, None, None, None, None
        )
        os_output.store(event)

        assert os_output._message_backlog[0].pop("@timestamp")
        assert os_output._message_backlog[0] == expected

    def test_store_sends_event_to_expected_index_with_date_pattern_if_index_missing_in_event(self):
        default_index = "default_index-%{YYYY-MM-DD}"
        event = {"field": "content"}

        formatted_date = arrow.now().format("YYYY-MM-DD")
        expected_index = re.sub(r"%{YYYY-MM-DD}", formatted_date, default_index)
        expected = {
            "_index": expected_index,
            "message": '{"field": "content"}',
            "reason": "Missing index in document",
        }

        os_output = OpenSearchOutput(
            ["host:123"], default_index, "error_index", 1, 5000, 0, None, None, None, None
        )
        os_output.store(event)

        assert os_output._message_backlog[0].pop("@timestamp")
        assert os_output._message_backlog[0] == expected

    def test_store_custom_sends_event_to_expected_index(self):
        custom_index = "custom_index"
        event = {"field": "content"}

        expected = {"field": "content", "_index": custom_index}

        os_output = OpenSearchOutput(
            ["host:123"], "default_index", "error_index", 1, 5000, 0, None, None, None, None
        )
        os_output.store_custom(event, custom_index)

        assert os_output._message_backlog[0] == expected

    def test_store_failed(self):
        error_index = "error_index"
        event_received = {"field": "received"}
        event = {"field": "content"}
        error_message = "error message"

        expected = {
            "error": error_message,
            "original": event_received,
            "processed": event,
            "_index": error_index,
            "@timestamp": str(datetime.now()),
        }

        os_output = OpenSearchOutput(
            ["host:123"], "default_index", error_index, 1, 5000, 0, None, None, None, None
        )
        os_output.store_failed(error_message, event_received, event)

        error_document = os_output._message_backlog[0]
        # timestamp is compared to be approximately the same,
        # since it is variable and then removed to compare the rest
        error_time = datetime.timestamp(arrow.get(error_document["@timestamp"]).datetime)
        expected_time = datetime.timestamp(arrow.get(error_document["@timestamp"]).datetime)
        assert isclose(error_time, expected_time)
        del error_document["@timestamp"]
        del expected["@timestamp"]

        assert error_document == expected

    def test_create_os_output_settings_contains_expected_values(self):
        expected = {
            "reason": "A reason for failed indexing",
            "_index": "default_index",
        }
        failed_document = self.os_output._build_failed_index_document(
            {"invalid_json": NotJsonSerializableMock(), "something_valid": "im_valid!"},
            "A reason for failed indexing",
        )
        assert "NotJsonSerializableMock" in failed_document.pop("message")
        assert failed_document.pop("@timestamp")
        assert failed_document == expected

    def test_build_failed_index_document(self):
        expected = {
            "reason": "A reason for failed indexing",
            "message": '{"foo": "bar"}',
            "_index": "default_index",
        }
        os_output = OpenSearchOutput(
            ["host:123"], "default_index", "error_index", 1, 5000, 0, None, None, None, None
        )
        failed_document = os_output._build_failed_index_document(
            {"foo": "bar"}, "A reason for failed indexing"
        )
        assert failed_document.pop("@timestamp")
        assert failed_document == expected

    @mock.patch(
        "logprep.connector.opensearch.output.helpers.bulk",
        side_effect=opensearchpy.SerializationError,
    )
    def test_write_to_os_calls_handle_serialization_error_if_serialization_error(self, _):
        self.os_output._handle_serialization_error = mock.MagicMock()
        self.os_output._write_to_os({"dummy": "event"})
        self.os_output._handle_serialization_error.assert_called()

    @mock.patch(
        "logprep.connector.opensearch.output.helpers.bulk",
        side_effect=opensearchpy.ConnectionError,
    )
    def test_write_to_os_calls_handle_connection_error_if_connection_error(self, _):
        self.os_output._handle_connection_error = mock.MagicMock()
        self.os_output._write_to_os({"dummy": "event"})
        self.os_output._handle_connection_error.assert_called()

    @mock.patch(
        "logprep.connector.opensearch.output.helpers.bulk",
        side_effect=opensearchpy.helpers.BulkIndexError,
    )
    def test_write_to_os_calls_handle_bulk_index_error_if_bulk_index_error(self, _):
        self.os_output._handle_bulk_index_error = mock.MagicMock()
        self.os_output._write_to_os({"dummy": "event"})
        self.os_output._handle_bulk_index_error.assert_called()

    @mock.patch("logprep.connector.opensearch.output.helpers.bulk")
    def test__handle_bulk_index_error_calls_bulk(self, fake_bulk):
        mock_bulk_index_error = mock.MagicMock()
        mock_bulk_index_error.errors = [
            {
                "index": {
                    "data": {"my": "document"},
                    "error": {"type": "myerrortype", "reason": "myreason"},
                }
            }
        ]
        self.os_output._handle_bulk_index_error(mock_bulk_index_error)
        fake_bulk.assert_called()

    @mock.patch("logprep.connector.opensearch.output.helpers.bulk")
    def test__handle_bulk_index_error_calls_bulk_with_error_documents(self, fake_bulk):
        mock_bulk_index_error = mock.MagicMock()
        mock_bulk_index_error.errors = [
            {
                "index": {
                    "data": {"my": "document"},
                    "error": {"type": "myerrortype", "reason": "myreason"},
                }
            }
        ]
        self.os_output._handle_bulk_index_error(mock_bulk_index_error)
        call_args = fake_bulk.call_args[0][1]
        error_document = call_args[0]
        assert "reason" in error_document
        assert "@timestamp" in error_document
        assert "_index" in error_document
        assert "message" in error_document
        assert error_document.get("reason") == "myerrortype: myreason"
        assert error_document.get("message") == json.dumps({"my": "document"})

    def test_write_to_os_calls_input_batch_finished_callback(self):
        self.os_output._input = mock.MagicMock()
        self.os_output._input.batch_finished_callback = mock.MagicMock()
        self.os_output._write_to_os({"dummy": "event"})
        self.os_output._input.batch_finished_callback.assert_called()

    def test_write_to_os_sets_processed_cnt(self):
        self.os_output._message_backlog_size = 2
        current_proccessed_cnt = self.os_output._processed_cnt
        self.os_output._write_to_os({"dummy": "event"})
        assert current_proccessed_cnt < self.os_output._processed_cnt

    def test_handle_connection_error_raises_fatal_output_error(self):
        with pytest.raises(FatalOutputError):
            self.os_output._handle_connection_error(mock.MagicMock())

    def test_handle_serialization_error_raises_fatal_output_error(self):
        with pytest.raises(FatalOutputError):
            self.os_output._handle_serialization_error(mock.MagicMock())

    @mock.patch("logprep.connector.opensearch.output.create_default_context")
    @mock.patch("logprep.connector.opensearch.output.OpenSearch")
    def test_ssl_context_check_hostname(self, mock_opensearch, mock_ssl_context):
        ssl_context_type = type("context", (), {"check_hostname": None})
        mock_ssl_context.return_value = ssl_context_type
        _ = OpenSearchOutput(
            ["host:123"],
            "default_index",
            "error_index",
            1,
            5000,
            0,
            None,
            None,
            "this/is/a/path",
            True,
        )

        mock_opensearch.assert_called_with(
            ["host:123"],
            scheme="https",
            http_auth=None,
            ssl_context=ssl_context_type,
            timeout=5000,
        )

        assert ssl_context_type.check_hostname
