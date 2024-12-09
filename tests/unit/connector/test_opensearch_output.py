# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-arguments
import copy
from unittest import mock

import pytest
from opensearchpy import OpenSearchException as SearchException
from opensearchpy import helpers

from logprep.abc.component import Component
from logprep.abc.output import CriticalOutputError
from logprep.factory import Factory
from tests.unit.connector.base import BaseOutputTestCase

helpers.parallel_bulk = mock.MagicMock()


class TestOpenSearchOutput(BaseOutputTestCase):
    CONFIG = {
        "type": "opensearch_output",
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
        event = {"field": "content"}

        self.object.store(event)

        assert self.object._message_backlog[0] == event
        assert self.object._message_backlog[0].get("_index") == config.get("default_index")

    def test_store_custom_sends_event_to_expected_index(self):
        custom_index = "custom_index"
        event = {"field": "content"}
        expected = {"field": "content", "_index": custom_index, "_op_type": "index"}
        config = copy.deepcopy(self.CONFIG)
        config["message_backlog_size"] = 2
        self.object = Factory.create({"opensearch_output": config})
        self.object.store_custom(event, custom_index)
        assert self.object._message_backlog[0] == expected

    def test_setup_registers_flush_timeout_tasks(self):
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

    def test_write_backlog_clears_message_backlog_on_success(self):
        self.object._message_backlog = [{"some": "event"}]
        self.object._write_backlog()
        assert len(self.object._message_backlog) == 0, "Message backlog should be cleared"

    def test_write_backlog_clears_message_backlog_on_failure(self):
        self.object._message_backlog = [{"some": "event"}]
        self.object._bulk = mock.MagicMock(
            side_effect=CriticalOutputError(mock.MagicMock(), "", "")
        )
        with pytest.raises(CriticalOutputError):
            self.object._write_backlog()
        assert len(self.object._message_backlog) == 0, "Message backlog should be cleared"

    def test_write_backlog_clears_failed_on_success(self):
        self.object._message_backlog = [{"some": "event"}]
        self.object._failed = [{"some": "event"}]
        with mock.patch("logprep.connector.opensearch.output.OpensearchOutput._bulk"):
            self.object._write_backlog()
        assert len(self.object._failed) == 0, "temporary failed backlog should be cleared"

    def test_write_backlog_clears_failed_on_failure(self):
        self.object._message_backlog = [{"some": "event"}]
        self.object._failed = [{"some": "event"}]
        with pytest.raises(CriticalOutputError):
            self.object._write_backlog()
        assert len(self.object._failed) == 0, "temporary failed backlog should be cleared"

    def test_write_backlog_creates_failed_event(self):
        error_message = "test error"
        event = {"some": "event"}
        helpers.parallel_bulk = mock.MagicMock(
            return_value=[(False, {"index": {"error": error_message}})]
        )
        self.object._message_backlog = [event]
        with pytest.raises(CriticalOutputError) as error:
            self.object._write_backlog()
        assert error.value.message == "failed to index"
        assert error.value.raw_input == [{"errors": error_message, "event": event}]

    def test_shut_down_clears_message_backlog(self):
        self.object._message_backlog = [{"some": "event"}]
        with mock.patch("logprep.connector.opensearch.output.OpensearchOutput._bulk"):
            self.object.shut_down()
        assert len(self.object._message_backlog) == 0, "Message backlog should be cleared"
