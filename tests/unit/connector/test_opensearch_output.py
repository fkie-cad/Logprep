# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-arguments
import copy
import json
import os
import re
import time
import uuid
from datetime import datetime
from math import isclose
from unittest import mock

import opensearchpy as search
import pytest
from opensearchpy import OpenSearchException as SearchException
from opensearchpy import helpers

from logprep.abc.component import Component
from logprep.abc.output import FatalOutputError
from logprep.connector.opensearch.output import OpensearchOutput
from logprep.factory import Factory
from logprep.util.time import TimeParser
from tests.unit.connector.base import BaseOutputTestCase


class NotJsonSerializableMock:
    pass


in_ci = os.environ.get("GITHUB_ACTIONS") == "true"

helpers.parallel_bulk = mock.MagicMock()
helpers.bulk = mock.MagicMock()


class TestOpenSearchOutput(BaseOutputTestCase):
    CONFIG = {
        "type": "opensearch_output",
        "hosts": ["localhost:9200"],
        "default_index": "default_index",
        "error_index": "error_index",
        "message_backlog_size": 1,
        "timeout": 5000,
    }

    def test_describe_returns_output(self):
        assert (
            self.object.describe()
            == "OpensearchOutput (Test Instance Name) - Opensearch Output: ['localhost:9200']"
        )

    def test_store_sends_to_default_index(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
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
        default_index = "default_index-%{%y-%m-%d}"
        event = {"field": "content"}

        formatted_date = TimeParser.now().strftime("%y-%m-%d")
        expected_index = re.sub(r"%{%y-%m-%d}", formatted_date, default_index)
        expected = {
            "_index": expected_index,
            "message": '{"field": "content"}',
            "reason": "Missing index in document",
        }
        config = copy.deepcopy(self.CONFIG)
        config["default_index"] = default_index
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
        self.object.store(event)

        assert self.object._message_backlog[0].pop("@timestamp")
        assert self.object._message_backlog[0] == expected

    def test_store_custom_sends_event_to_expected_index(self):
        custom_index = "custom_index"
        event = {"field": "content"}
        expected = {"field": "content", "_index": custom_index}
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
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

        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
        self.object.store_failed(error_message, event_received, event)

        error_document = self.object._message_backlog[0]
        # timestamp is compared to be approximately the same,
        # since it is variable and then removed to compare the rest
        error_time = datetime.timestamp(TimeParser.from_string(error_document["@timestamp"]))
        expected_time = datetime.timestamp(TimeParser.from_string(error_document["@timestamp"]))
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
        "opensearchpy.helpers.parallel_bulk",
        side_effect=search.SerializationError,
    )
    def test_write_to_search_context_calls_handle_serialization_error_if_serialization_error(
        self, _
    ):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 1
        self.object = Factory.create({"opensearch_output": config})
        self.object._handle_serialization_error = mock.MagicMock()
        self.object._message_backlog.append({"dummy": "event"})
        self.object._write_to_search_context()
        self.object._handle_serialization_error.assert_called()

    @mock.patch(
        "opensearchpy.helpers.parallel_bulk",
        side_effect=search.ConnectionError(-1),
    )
    @mock.patch("time.sleep", mock.MagicMock())  # to speed up test execution
    def test_write_to_search_context_calls_handle_connection_error_if_connection_error(self, _):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 1
        self.object = Factory.create({"opensearch_output": config})
        self.object._handle_connection_error = mock.MagicMock()
        self.object._message_backlog.append({"dummy": "event"})
        self.object._write_to_search_context()
        self.object._handle_connection_error.assert_called()

    @mock.patch(
        "opensearchpy.helpers.parallel_bulk",
        side_effect=helpers.BulkIndexError,
    )
    def test_write_to_search_context_calls_handle_bulk_index_error_if_bulk_index_error(self, _):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 1
        self.object = Factory.create({"opensearch_output": config})
        self.object._handle_bulk_index_error = mock.MagicMock()
        self.object._message_backlog.append({"dummy": "event"})
        self.object._write_to_search_context()
        self.object._handle_bulk_index_error.assert_called()

    @mock.patch("opensearchpy.helpers.parallel_bulk")
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

    @mock.patch("opensearchpy.helpers.parallel_bulk")
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
        error_document = fake_bulk.call_args.kwargs.get("actions").pop()
        assert "reason" in error_document
        assert "@timestamp" in error_document
        assert "_index" in error_document
        assert "message" in error_document
        assert error_document.get("reason") == "myerrortype: myreason"
        assert error_document.get("message") == json.dumps({"my": "document"})

    @pytest.mark.parametrize(
        "status_code, error, error_info, messages, discarded_cnt, exception",
        [
            (
                429,
                "circuit_breaking_exception",
                {"anything": "anything"},
                [{"foo": "*" * 500}],
                1,
                None,
            ),
            (
                429,
                "circuit_breaking_exception",
                {"anything": "anything"},
                [{"foo": "bar"}, {"bar": "baz"}],
                0,
                FatalOutputError,
            ),
            (
                429,
                "circuit_breaking_exception",
                {"anything": "anything"},
                [{"foo": "*" * 500}, {"bar": "baz"}],
                1,
                None,
            ),
            (
                429,
                "circuit_breaking_exception",
                {"anything": "anything"},
                [{"foo": "*" * 500}, {"bar": "*" * 500}],
                2,
                None,
            ),
            (
                123,
                "circuit_breaking_exception",
                {"anything": "anything"},
                [{"foo": "*" * 500}],
                1,
                FatalOutputError,
            ),
            (
                429,
                "wrong_exception",
                {"anything": "anything"},
                [{"foo": "*" * 500}],
                1,
                FatalOutputError,
            ),
            (
                429,
                "rejected_execution_exception",
                {"invalid": "error"},
                [{"foo": "*" * 500}],
                1,
                FatalOutputError,
            ),
            (
                429,
                "rejected_execution_exception",
                {"error": {"reason": "wrong_reason"}},
                [{"foo": "*" * 500}],
                1,
                FatalOutputError,
            ),
            (
                429,
                "rejected_execution_exception",
                {
                    "error": {
                        "reason": "... "
                        "coordinating_operation_bytes=9, max_coordinating_and_primary_bytes=1 "
                        "..."
                    }
                },
                [{"foo": "*" * 500}],
                1,
                None,
            ),
            (
                429,
                "rejected_execution_exception",
                {
                    "error": {
                        "reason": "... "
                        "coordinating_operation_bytes=1, max_coordinating_and_primary_bytes=9 "
                        "..."
                    }
                },
                [{"foo": "*" * 500}],
                1,
                FatalOutputError,
            ),
        ],
    )
    def test_handle_transport_error_calls_bulk_with_error_documents(
        self, status_code, error, error_info, messages, discarded_cnt, exception
    ):
        config = copy.deepcopy(self.CONFIG)
        config["maximum_message_size_mb"] = 5 * 10**-4
        self.object = Factory.create({"opensearch_output": config})
        mock_transport_error = search.exceptions.TransportError(status_code, error, error_info)

        if exception:
            with pytest.raises(exception):
                self.object._handle_transport_error(mock_transport_error)
        else:
            self.object._message_backlog = messages
            self.object._handle_transport_error(mock_transport_error)
            above_limit = []
            under_limit = []
            for message in self.object._message_backlog:
                if message.get("_index") == "error_index":
                    assert message.get("error", "").startswith(
                        "Discarded message that is larger than the allowed size limit"
                    )
                    assert len(message.get("processed_snipped", "")) <= 1000
                    assert message.get("processed_snipped", "").endswith(" ...")
                    above_limit.append(message)
                else:
                    under_limit.append(message)
            assert len(above_limit) == discarded_cnt
            assert len(above_limit) + len(under_limit) == len(self.object._message_backlog)

    def test_handle_connection_error_raises_fatal_output_error(self):
        with pytest.raises(FatalOutputError):
            self.object._handle_connection_error(mock.MagicMock())

    def test_handle_serialization_error_raises_fatal_output_error(self):
        with pytest.raises(FatalOutputError):
            self.object._handle_serialization_error(mock.MagicMock())

    def test_setup_registers_flush_timout_tasks(self):
        job_count = len(Component._scheduler.jobs)
        with mock.patch.object(self.object, "_search_context", new=mock.MagicMock()):
            self.object.setup()
        assert len(Component._scheduler.jobs) == job_count + 1

    def test_message_backlog_is_not_written_if_message_backlog_size_not_reached(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
        assert len(self.object._message_backlog) == 0
        with mock.patch(
            "logprep.connector.opensearch.output.OpensearchOutput._write_backlog"
        ) as mock_write_backlog:
            self.object.store({"test": "event"})
        mock_write_backlog.assert_not_called()

    def test_message_backlog_is_cleared_after_it_was_written(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 1
        self.object = Factory.create({"opensearch_output": config})
        self.object.store({"event": "test_event"})
        assert len(self.object._message_backlog) == 0

    @pytest.mark.skip(reason="This test is only for local debugging")
    def test_opensearch_parallel_bulk(self):
        config = {
            "type": "opensearch_output",
            "hosts": ["localhost:9200"],
            "default_index": "default_index",
            "error_index": "error_index",
            "message_backlog_size": 1,
            "timeout": 5000,
        }
        output: OpensearchOutput = Factory.create({"opensearch_output": config})
        uuid_str = str(uuid.uuid4())
        result = output._search_context.search(
            index="defaultindex", body={"query": {"match": {"foo": uuid_str}}}
        )
        len_before = len(result["hits"]["hits"])
        output._message_backlog = [{"foo": uuid_str, "_index": "defaultindex"}]
        output._write_backlog()
        time.sleep(1)
        result = output._search_context.search(
            index="defaultindex", body={"query": {"match": {"foo": uuid_str}}}
        )
        assert len(result["hits"]["hits"]) > len_before

    @mock.patch(
        "logprep.connector.opensearch.output.OpensearchOutput._search_context",
        new=mock.MagicMock(),
    )
    @mock.patch("inspect.getmembers", return_value=[("mock_prop", lambda: None)])
    def test_setup_populates_cached_properties(self, mock_getmembers):
        self.object.setup()
        mock_getmembers.assert_called_with(self.object)

    @mock.patch(
        "opensearchpy.helpers.parallel_bulk",
        side_effect=search.TransportError(429, "rejected_execution_exception", {}),
    )
    @mock.patch("time.sleep")
    def test_write_backlog_fails_if_all_retries_are_exceeded(self, _, mock_sleep):
        config = copy.deepcopy(self.CONFIG)
        config["maximum_message_size_mb"] = 1
        config["max_retries"] = 5
        self.object = Factory.create({"opensearch_output": config})
        self.object._message_backlog = [{"some": "event"}]
        with pytest.raises(
            FatalOutputError, match="Opensearch too many requests, all parallel bulk retries failed"
        ):
            self.object._write_backlog()
        assert mock_sleep.call_count == 6  # one initial try + 5 retries
        assert self.object._message_backlog == [{"some": "event"}]

    @mock.patch("time.sleep")
    def test_write_backlog_is_successful_after_two_retries(self, mock_sleep):
        side_effects = [
            search.TransportError(429, "rejected_execution_exception", {}),
            search.TransportError(429, "rejected_execution_exception", {}),
            [],
        ]
        with mock.patch("opensearchpy.helpers.parallel_bulk", side_effect=side_effects):
            config = copy.deepcopy(self.CONFIG)
            config["maximum_message_size_mb"] = 1
            config["max_retries"] = 5
            self.object = Factory.create({"opensearch_output": config})
            self.object._message_backlog = [{"some": "event"}]
            self.object._write_backlog()
            assert mock_sleep.call_count == 2
            assert self.object._message_backlog == []

    def test_health_returns_true_on_success(self):
        self.object._search_context = mock.MagicMock()
        self.object._search_context.cluster.health.return_value = {"status": "green"}
        assert self.object.health()

    @pytest.mark.parametrize("exception", [SearchException, ConnectionError])
    def test_health_returns_false_on_failure(self, exception):
        self.object._search_context = mock.MagicMock()
        self.object._search_context.cluster.health.side_effect = exception
        assert not self.object.health()

    def test_health_logs_on_failure(self):
        self.object._search_context = mock.MagicMock()
        self.object._search_context.cluster.health.side_effect = SearchException
        with mock.patch("logging.Logger.error") as mock_error:
            assert not self.object.health()
            mock_error.assert_called()

    def test_health_counts_metrics_on_failure(self):
        self.object.metrics.number_of_errors = 0
        self.object._search_context = mock.MagicMock()
        self.object._search_context.cluster.health.side_effect = SearchException
        assert not self.object.health()
        assert self.object.metrics.number_of_errors == 1

    def test_health_returns_false_on_cluster_status_not_green(self):
        self.object._search_context = mock.MagicMock()
        self.object._search_context.cluster.health.return_value = {"status": "yellow"}
        assert not self.object.health()
