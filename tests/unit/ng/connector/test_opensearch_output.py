# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-arguments
# pylint: disable=line-too-long

import copy
import re
from unittest import mock

import pytest
from opensearchpy import OpenSearchException as SearchException
from opensearchpy import helpers

from logprep.abc.component import Component
from logprep.factory import Factory
from logprep.ng.connector.opensearch.output import BulkError
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.connector.base import BaseOutputTestCase

helpers.parallel_bulk = mock.MagicMock()


class TestOpenSearchOutput(BaseOutputTestCase):
    CONFIG = {
        "type": "ng_opensearch_output",
        "hosts": ["localhost:9200"],
        "default_index": "default_index",
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
        event = LogEvent({"field": "content"}, original=b"")

        self.object.store(event)

        assert self.object._message_backlog[0] == event
        assert event.data.get("_index") == config.get("default_index")

    def test_store_custom_sends_event_to_expected_index(self):
        custom_index = "custom_index"
        event = LogEvent({"field": "content"}, original=b"")
        expected = {"field": "content", "_index": custom_index, "_op_type": "index"}
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
        self.object.store_custom(event, custom_index)
        assert self.object._message_backlog[0] == event
        assert event.data == expected

    def test_setup_registers_flush_timeout_tasks(self):
        job_count = len(Component._scheduler.jobs)
        with mock.patch.object(self.object, "_search_context"):
            with mock.patch.object(self.object, "flush") as mock_flush:
                self.object.setup()
        assert len(Component._scheduler.jobs) == job_count + 1
        Component._scheduler.run_all()
        mock_flush.assert_called_once()

    def test_message_backlog_is_not_written_if_message_backlog_size_not_reached(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
        assert len(self.object._message_backlog) == 0
        with mock.patch.object(self.object, "flush") as mock_flush:
            self.object.store(LogEvent({"test": "event"}, original=b""))
        mock_flush.assert_not_called()

    def test_message_backlog_is_cleared_after_it_was_written(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 1
        self.object = Factory.create({"opensearch_output": config})
        self.object.store(LogEvent({"event": "test_event"}, original=b""))
        assert len(self.object._message_backlog) == 0

    @mock.patch(
        "logprep.connector.opensearch.output.OpensearchOutput._search_context",
        new=mock.MagicMock(),
    )
    @mock.patch("inspect.getmembers", return_value=[("mock_prop", lambda: None)])
    def test_setup_populates_cached_properties(self, mock_getmembers):
        self.object.setup()
        mock_getmembers.assert_called_with(self.object)

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

    def test_flush_clears_message_backlog_on_success(self):
        event = LogEvent({"some": "event"}, original=b"")
        self.object._message_backlog = [event]
        self.object.flush()
        assert len(self.object._message_backlog) == 0, "Message backlog should be cleared"

    def test_store_changes_state_successful_path(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
        state, expected_state = EventStateType.PROCESSED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )

        return_value = [(True, {"index": {"_id": "1"}})]
        self.object.store(event)
        assert event.state == EventStateType.STORED_IN_OUTPUT
        with mock.patch("opensearchpy.helpers.parallel_bulk") as mock_bulk:
            mock_bulk.return_value = return_value
            self.object.flush()
        assert event.state == expected_state

    def test_store_changes_state_failed_event_with_unsuccessful_path(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
        state, expected_state = EventStateType.FAILED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )

        return_value = [(True, {"index": {"_id": "1"}})]
        self.object.store(event)
        assert event.state == EventStateType.STORED_IN_ERROR
        with mock.patch("opensearchpy.helpers.parallel_bulk") as mock_bulk:
            mock_bulk.return_value = return_value
            self.object.flush()
        assert event.state == expected_state

    def test_store_custom_changes_state_successful_path(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
        state, expected_state = EventStateType.PROCESSED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )

        return_value = [(True, {"index": {"_id": "1"}})]
        self.object.store_custom(event, "custom_index")
        assert event.state == EventStateType.STORED_IN_OUTPUT
        with mock.patch("opensearchpy.helpers.parallel_bulk") as mock_bulk:
            mock_bulk.return_value = return_value
            self.object.flush()
        assert event.state == expected_state

    def test_store_custom_changes_state_failed_event_with_unsuccessful_path(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
        state, expected_state = EventStateType.FAILED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )

        return_value = [(True, {"index": {"_id": "1"}})]
        self.object.store_custom(event, "custom_index")
        assert event.state == EventStateType.STORED_IN_ERROR
        with mock.patch("opensearchpy.helpers.parallel_bulk") as mock_bulk:
            mock_bulk.return_value = return_value
            self.object.flush()
        assert event.state == expected_state

    def test_store_handles_errors(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        with mock.patch.object(self.object, "_write_to_search_context") as mock_write:
            mock_write.side_effect = Exception("test error")
            self.object.store(event)
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

    def test_store_custom_handles_errors(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        with mock.patch.object(self.object, "_write_to_search_context") as mock_write:
            mock_write.side_effect = Exception("test error")
            self.object.store_custom(event, "custom_index")
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED, f"{event.state} should be FAILED"

    def test_store_handles_errors_failed_event(self):
        """you have to override this method in some output implementations depending on the implementation of the store and write_backlog methods."""
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.FAILED)
        with mock.patch.object(self.object, "_write_to_search_context") as mock_write:
            mock_write.side_effect = Exception("test error")
            self.object.store(event)
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

    def test_store_custom_handles_errors_failed_event(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.FAILED)
        with mock.patch.object(self.object, "_write_to_search_context") as mock_write:
            mock_write.side_effect = Exception("test error")
            self.object.store_custom(event, "custom_index")
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED, f"{event.state} should be FAILED"

    def test_flush_handles_failed_bulk_operations(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 3
        self.object = Factory.create({"opensearch_output": config})
        event1 = LogEvent(
            {"message": "test message"},
            original=b"",
            state=EventStateType.PROCESSED,
        )
        event2 = LogEvent(
            {"message": "test message"},
            original=b"",
            state=EventStateType.PROCESSED,
        )
        # helpers.parallel_bulk returns an Iterator of tuples (success, item)
        return_value = [(True, {"index": {"_id": "1"}}), (False, {"index": {"_id": "1"}})]
        self.object.store(event1)
        self.object.store(event2)
        assert event1.state == EventStateType.STORED_IN_OUTPUT
        assert event2.state == EventStateType.STORED_IN_OUTPUT
        with mock.patch("opensearchpy.helpers.parallel_bulk") as mock_bulk:
            mock_bulk.return_value = return_value
            self.object.flush()
        assert event1.state == EventStateType.DELIVERED
        assert event2.state == EventStateType.FAILED
        assert len(event2.errors) == 1

    def test_flush_creates_bulk_error(self):
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 3
        config["default_op_type"] = "create"
        self.object = Factory.create({"opensearch_output": config})
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=EventStateType.PROCESSED,
        )
        # helpers.parallel_bulk returns an Iterator of tuples (success, item)
        return_value = [
            (
                False,
                {
                    "create": {
                        "error": "Failed to index document",
                        "status": "503",
                        "exception": "Service Unavailable",
                    }
                },
            )
        ]
        self.object.store(event)
        assert event.state == EventStateType.STORED_IN_OUTPUT
        with mock.patch("opensearchpy.helpers.parallel_bulk") as mock_bulk:
            mock_bulk.return_value = return_value
            self.object.flush()
        assert event.state == EventStateType.FAILED
        assert len(event.errors) == 1
        error = event.errors[0]
        assert isinstance(error, BulkError)
        assert re.search("Failed to index document", str(error))
        assert re.search("503", str(error))
        assert re.search("Service Unavailable", str(error))

    def test_thread_count_is_passed_to_client(self):
        config = copy.deepcopy(self.CONFIG)
        config["thread_count"] = 42
        self.object = Factory.create({"opensearch_output": config})

        event = LogEvent({"field": "content"}, original=b"")

        with mock.patch("opensearchpy.helpers.parallel_bulk") as mock_bulk:
            mock_bulk.return_value = [(True, None)]
            self.object.store(event)

            mock_bulk.assert_called_once()
            assert mock_bulk.call_args[1]["thread_count"] == 42
