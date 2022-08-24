# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
import re
from datetime import datetime
from json import loads, dumps
from math import isclose
from unittest import mock

import arrow
import elasticsearch
import elasticsearch.helpers
from pytest import fail

from logprep.output.es_output import ElasticsearchOutput
from logprep.output.output import CriticalOutputError


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


elasticsearch.helpers.bulk = mock_bulk


class TestElasticsearchOutput:
    def setup_method(self, _):
        self.es_output = ElasticsearchOutput(
            ["host:123"], "default_index", "error_index", 1, 5000, 0, None, None, None
        )

    def test_implements_abstract_methods(self):
        try:
            ElasticsearchOutput(
                ["host:123"], "default_index", "error_index", 2, 5000, 0, None, None, None
            )
        except TypeError as err:
            fail(f"Must implement abstract methods: {str(err)}")

    def test_describe_endpoint_returns_elasticsearch_output(self):
        assert self.es_output.describe_endpoint() == "Elasticsearch Output: ['host:123']"

    def test_store_sends_event_to_expected_index_if_index_missing_in_event(self):
        default_index = "target_index"
        event = {"field": "content"}
        expected = {
            "_index": default_index,
            "message": '{"field": "content"}',
            "reason": "Missing index in document",
        }

        es_output = ElasticsearchOutput(
            ["host:123"], default_index, "error_index", 1, 5000, 0, None, None, None
        )
        es_output.store(event)

        assert es_output._message_backlog[0].pop("@timestamp")
        assert es_output._message_backlog[0] == expected

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

        es_output = ElasticsearchOutput(
            ["host:123"], default_index, "error_index", 1, 5000, 0, None, None, None
        )
        es_output.store(event)

        assert es_output._message_backlog[0].pop("@timestamp")
        assert es_output._message_backlog[0] == expected

    def test_store_custom_sends_event_to_expected_index(self):
        custom_index = "custom_index"
        event = {"field": "content"}

        expected = {"field": "content", "_index": custom_index}

        es_output = ElasticsearchOutput(
            ["host:123"], "default_index", "error_index", 1, 5000, 0, None, None, None
        )
        es_output.store_custom(event, custom_index)

        assert es_output._message_backlog[0] == expected

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

        es_output = ElasticsearchOutput(
            ["host:123"], "default_index", error_index, 1, 5000, 0, None, None, None
        )
        es_output.store_failed(error_message, event_received, event)

        error_document = es_output._message_backlog[0]
        # timestamp is compared to be approximately the same,
        # since it is variable and then removed to compare the rest
        error_time = datetime.timestamp(arrow.get(error_document["@timestamp"]).datetime)
        expected_time = datetime.timestamp(arrow.get(error_document["@timestamp"]).datetime)
        assert isclose(error_time, expected_time)
        del error_document["@timestamp"]
        del expected["@timestamp"]

        assert error_document == expected

    def test_create_es_output_settings_contains_expected_values(self):
        expected = {
            "reason": "A reason for failed indexing",
            "_index": "default_index",
        }
        failed_document = self.es_output._build_failed_index_document(
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
        es_output = ElasticsearchOutput(
            ["host:123"], "default_index", "error_index", 1, 5000, 0, None, None, None
        )
        failed_document = es_output._build_failed_index_document(
            {"foo": "bar"}, "A reason for failed indexing"
        )
        assert failed_document.pop("@timestamp")
        assert failed_document == expected

    @mock.patch(
        "logprep.output.es_output.helpers.bulk", side_effect=elasticsearch.SerializationError
    )
    def test_write_to_es_calls_handle_serialization_error_if_serialization_error(self, _):
        self.es_output._handle_serialization_error = mock.MagicMock()
        self.es_output._write_to_es({"dummy": "event"})
        self.es_output._handle_serialization_error.assert_called()

    @mock.patch("logprep.output.es_output.helpers.bulk", side_effect=elasticsearch.ConnectionError)
    def test_write_to_es_calls_handle_connection_error_if_connection_error(self, _):
        self.es_output._handle_connection_error = mock.MagicMock()
        self.es_output._write_to_es({"dummy": "event"})
        self.es_output._handle_connection_error.assert_called()

    @mock.patch(
        "logprep.output.es_output.helpers.bulk", side_effect=elasticsearch.helpers.BulkIndexError
    )
    def test_write_to_es_calls_handle_bulk_index_error_if_bulk_index_error(self, _):
        self.es_output._handle_bulk_index_error = mock.MagicMock()
        self.es_output._write_to_es({"dummy": "event"})
        self.es_output._handle_bulk_index_error.assert_called()
