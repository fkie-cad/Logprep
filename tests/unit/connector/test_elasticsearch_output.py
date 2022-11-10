# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
from copy import deepcopy
import json
import re
import pytest
from datetime import datetime
from json import loads, dumps
from math import isclose
from unittest import mock

import arrow
import elasticsearch
import elasticsearch.helpers

from logprep.factory import Factory
from logprep.abc.output import CriticalOutputError, FatalOutputError
from tests.unit.connector.base import BaseOutputTestCase


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


class TestElasticsearchOutput(BaseOutputTestCase):

    CONFIG = {
        "type": "elasticsearch_output",
        "hosts": ["host:123"],
        "default_index": "default_index",
        "error_index": "error_index",
        "message_backlog_size": 1,
        "timeout": 5000,
    }

    def test_describe_returns_elasticsearch_output(self):
        assert (
            self.object.describe()
            == "ElasticsearchOutput (Test Instance Name) - ElasticSearch Output: ['host:123']"
        )

    def test_store_sends_to_default_index(self):
        event = {"field": "content"}
        expected = {
            "_index": "default_index",
            "message": '{"field": "content"}',
            "reason": "Missing index in document",
        }
        self.object.store(event)

        assert self.object._message_backlog[0].pop("@timestamp")
        assert self.object._message_backlog[0] == expected

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
        es_config = deepcopy(self.CONFIG)
        es_config.update({"default_index": default_index})
        es_output = Factory.create({"elasticsearch": es_config}, self.logger)
        es_output.store(event)

        assert es_output._message_backlog[0].pop("@timestamp")
        assert es_output._message_backlog[0] == expected

    def test_store_custom_sends_event_to_expected_index(self):
        custom_index = "custom_index"
        event = {"field": "content"}
        expected = {"field": "content", "_index": custom_index}
        self.object.store_custom(event, custom_index)
        assert self.object._message_backlog[0] == expected

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

        self.object.store_failed(error_message, event_received, event)

        error_document = self.object._message_backlog[0]
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
        failed_document = self.object._build_failed_index_document(
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
        failed_document = self.object._build_failed_index_document(
            {"foo": "bar"}, "A reason for failed indexing"
        )
        assert failed_document.pop("@timestamp")
        assert failed_document == expected

    @mock.patch(
        "logprep.connector.elasticsearch.output.helpers.bulk",
        side_effect=elasticsearch.SerializationError,
    )
    def test_write_to_search_context_calls_handle_serialization_error_if_serialization_error(
        self, _
    ):
        self.object._handle_serialization_error = mock.MagicMock()
        self.object._write_to_search_context({"dummy": "event"})
        self.object._handle_serialization_error.assert_called()

    @mock.patch(
        "logprep.connector.elasticsearch.output.helpers.bulk",
        side_effect=elasticsearch.ConnectionError,
    )
    def test_write_to_search_context_calls_handle_connection_error_if_connection_error(self, _):
        self.object._handle_connection_error = mock.MagicMock()
        self.object._write_to_search_context({"dummy": "event"})
        self.object._handle_connection_error.assert_called()

    @mock.patch(
        "logprep.connector.elasticsearch.output.helpers.bulk",
        side_effect=elasticsearch.helpers.BulkIndexError,
    )
    def test_write_to_search_context_calls_handle_bulk_index_error_if_bulk_index_error(self, _):
        self.object._handle_bulk_index_error = mock.MagicMock()
        self.object._write_to_search_context({"dummy": "event"})
        self.object._handle_bulk_index_error.assert_called()

    @mock.patch("logprep.connector.elasticsearch.output.helpers.bulk")
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
        self.object._handle_bulk_index_error(mock_bulk_index_error)
        fake_bulk.assert_called()

    @mock.patch("logprep.connector.elasticsearch.output.helpers.bulk")
    def test_handle_bulk_index_error_calls_bulk_with_error_documents(self, fake_bulk):
        mock_bulk_index_error = mock.MagicMock()
        mock_bulk_index_error.errors = [
            {
                "index": {
                    "data": {"my": "document"},
                    "error": {"type": "myerrortype", "reason": "myreason"},
                }
            }
        ]
        self.object._handle_bulk_index_error(mock_bulk_index_error)
        call_args = fake_bulk.call_args[0][1]
        error_document = call_args[0]
        assert "reason" in error_document
        assert "@timestamp" in error_document
        assert "_index" in error_document
        assert "message" in error_document
        assert error_document.get("reason") == "myerrortype: myreason"
        assert error_document.get("message") == json.dumps({"my": "document"})

    def test_write_to_search_context_sets_processed_cnt(self):
        es_config = deepcopy(self.CONFIG)
        es_config.update({"message_backlog_size": 2})
        es_output = Factory.create({"elasticsearch": es_config}, self.logger)
        current_proccessed_cnt = es_output._processed_cnt
        es_output._write_to_search_context({"dummy": "event"})
        assert current_proccessed_cnt < es_output._processed_cnt

    def test_handle_connection_error_raises_fatal_output_error(self):
        with pytest.raises(FatalOutputError):
            self.object._handle_connection_error(mock.MagicMock())

    def test_handle_serialization_error_raises_fatal_output_error(self):
        with pytest.raises(FatalOutputError):
            self.object._handle_serialization_error(mock.MagicMock())
