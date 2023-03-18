# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
import json
from json import dumps, loads
from unittest import mock

import opensearchpy as search
import pytest
from opensearchpy import OpenSearchException as SearchException
from opensearchpy import helpers

from logprep.abc.component import Component
from logprep.abc.output import CriticalOutputError, FatalOutputError
from tests.unit.connector.test_elasticsearch_output import (
    TestElasticsearchOutput,
    mock_bulk,
)

helpers.bulk = mock_bulk


class TestOpenSearchOutput(TestElasticsearchOutput):
    CONFIG = {
        "type": "opensearch_output",
        "hosts": ["host:123"],
        "default_index": "default_index",
        "error_index": "error_index",
        "message_backlog_size": 1,
        "timeout": 5000,
    }

    def test_describe_returns_output(self):
        assert (
            self.object.describe()
            == "OpensearchOutput (Test Instance Name) - Opensearch Output: ['host:123']"
        )

    @mock.patch(
        "opensearchpy.helpers.bulk",
        side_effect=search.SerializationError,
    )
    def test_write_to_search_context_calls_handle_serialization_error_if_serialization_error(
        self, _
    ):
        self.object._config.message_backlog_size = 1
        self.object._handle_serialization_error = mock.MagicMock()
        self.object._write_to_search_context({"dummy": "event"})
        self.object._handle_serialization_error.assert_called()

    @mock.patch(
        "opensearchpy.helpers.bulk",
        side_effect=search.ConnectionError,
    )
    def test_write_to_search_context_calls_handle_connection_error_if_connection_error(self, _):
        self.object._config.message_backlog_size = 1
        self.object._handle_connection_error = mock.MagicMock()
        self.object._write_to_search_context({"dummy": "event"})
        self.object._handle_connection_error.assert_called()

    @mock.patch(
        "opensearchpy.helpers.bulk",
        side_effect=search.helpers.BulkIndexError,
    )
    def test_write_to_search_context_calls_handle_bulk_index_error_if_bulk_index_error(self, _):
        self.object._config.message_backlog_size = 1
        self.object._handle_bulk_index_error = mock.MagicMock()
        self.object._write_to_search_context({"dummy": "event"})
        self.object._handle_bulk_index_error.assert_called()

    @mock.patch("opensearchpy.helpers.bulk")
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

    @mock.patch("opensearchpy.helpers.bulk")
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
