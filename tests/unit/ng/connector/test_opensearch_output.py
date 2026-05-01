# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-arguments
# pylint: disable=line-too-long

import re
from collections.abc import Iterable
from unittest import mock

import pytest
from opensearchpy import AsyncOpenSearch
from opensearchpy import OpenSearchException as SearchException
from opensearchpy import helpers

from logprep.ng.connector.opensearch.output import BulkError, OpensearchOutput
from logprep.ng.event.log_event import LogEvent
from tests.unit.ng.connector.base import BaseOutputTestCase

helpers.parallel_bulk = mock.MagicMock()


class TestOpenSearchOutput(BaseOutputTestCase[OpensearchOutput]):
    CONFIG = {
        "type": "ng_opensearch_output",
        "hosts": ["localhost:9200"],
        "default_index": "default_index",
        "message_backlog_size": 1,
        "timeout": 5000,
    }

    @pytest.fixture
    def mock_search_context(self):
        # TODO do we need the whole path, or can we make this prettier?
        with mock.patch(
            "logprep.ng.connector.opensearch.output.AsyncOpenSearch", spec=AsyncOpenSearch
        ) as mock_search_context:
            mock_search_context.return_value = mock_search_context
            mock_search_context.cluster = mock.MagicMock()
            mock_search_context.cluster.health = mock.AsyncMock()
            mock_search_context.cluster.health.return_value = mock.MagicMock()
            yield mock_search_context

    @pytest.fixture
    def mock_async_streaming_bulk_results(self, request):
        data = request.param if hasattr(request, "param") else []
        return data

    @pytest.fixture
    def mock_async_streaming_bulk(self, mock_async_streaming_bulk_results):
        # TODO do we need the whole path, or can we make this prettier?
        with mock.patch(
            "logprep.ng.connector.opensearch.output.helpers.async_streaming_bulk",
            spec=helpers.async_streaming_bulk,
        ) as mock_async_streaming_bulk:

            async def gen_return_values(*_, **__):
                for item in mock_async_streaming_bulk_results:
                    yield item

            mock_async_streaming_bulk.side_effect = gen_return_values
            yield mock_async_streaming_bulk

    @pytest.fixture(autouse=True)
    def autouse_central_fixtures(self, mock_search_context, mock_async_streaming_bulk):
        yield mock_search_context, mock_async_streaming_bulk  # return technically not required

    @staticmethod
    def set_async_streaming_bulk_results(tuples: Iterable[tuple[bool, dict]]):
        return pytest.mark.parametrize("mock_async_streaming_bulk_results", [tuples], indirect=True)

    # ==========================================================================

    async def test_describe_returns_output(self):
        assert (
            self.object.describe()
            == "OpensearchOutput (Test Instance Name) - Opensearch Output: ['localhost:9200']"
        )

    @set_async_streaming_bulk_results([(True, {})])
    async def test_store_sends_to_default_index(self):
        event = LogEvent({"field": "content"}, original=b"")

        await self.object.setup()
        await self.object.store_batch([event])

        assert len(event.errors) == 0
        assert event.data.get("_index") == self.CONFIG.get("default_index")

    @set_async_streaming_bulk_results([(True, {})])
    async def test_store_custom_sends_event_to_expected_index(self):
        event = LogEvent({"field": "content"}, original=b"")

        await self.object.setup()
        await self.object.store_batch([event], "custom_index")

        assert len(event.errors) == 0
        assert event.data == {"field": "content", "_index": "custom_index", "_op_type": "index"}

    @mock.patch("inspect.getmembers", return_value=[("mock_prop", lambda: None)])
    async def test_setup_populates_cached_properties(self, mock_getmembers):
        await self.object.setup()
        mock_getmembers.assert_called_with(self.object)

    async def test_health_returns_true_on_success(self, mock_search_context):
        mock_search_context.cluster.health.return_value = {"status": "green"}
        await self.object.setup()
        assert await self.object.health()

    @pytest.mark.parametrize("exception", [SearchException, ConnectionError])
    async def test_health_returns_false_on_failure(self, exception, mock_search_context):
        mock_search_context.cluster.health.side_effect = exception
        await self.object.setup()
        assert not await self.object.health()

    async def test_health_logs_on_failure(self, mock_search_context):
        mock_search_context.cluster.health.side_effect = SearchException
        await self.object.setup()
        with mock.patch("logging.Logger.error") as mock_error:
            assert not await self.object.health()
            mock_error.assert_called()

    async def test_health_counts_metrics_on_failure(self, mock_search_context):
        self.object.metrics.number_of_errors = 0
        mock_search_context.cluster.health.side_effect = SearchException
        await self.object.setup()
        assert not await self.object.health()
        assert self.object.metrics.number_of_errors == 1

    async def test_health_returns_false_on_cluster_status_not_green(self, mock_search_context):
        mock_search_context.cluster.health.return_value = {"status": "yellow"}
        await self.object.setup()
        assert not await self.object.health()

    async def test_store_handles_errors(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"")
        await self.object.setup()
        with mock.patch.object(self.object, "_bulk") as mock_write:
            mock_write.side_effect = Exception("test error")
            await self.object.store_batch([event])
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1

    async def test_store_custom_handles_errors(self):
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"")
        await self.object.setup()
        with mock.patch.object(self.object, "_bulk") as mock_write:
            mock_write.side_effect = Exception("test error")
            await self.object.store_batch([event], "custom_index")
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1

    @set_async_streaming_bulk_results(
        [(True, {"index": {"_id": "1"}}), (False, {"index": {"_id": "1"}})]
    )
    async def test_store_batch_handles_failed_bulk_operations(self):
        event1 = LogEvent({"message": "test message"}, original=b"")
        event2 = LogEvent({"message": "test message"}, original=b"")
        await self.object.setup()
        await self.object.store_batch([event1, event2])
        assert len(event1.errors) == 0
        assert len(event2.errors) == 1

    @set_async_streaming_bulk_results(
        [
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
    )
    async def test_bulk_creates_bulk_error(self):
        event = LogEvent({"message": "test message"}, original=b"")
        await self.object.setup()
        await self.object.store_batch([event])
        assert len(event.errors) == 1
        error = event.errors[0]
        assert isinstance(error, BulkError)
        assert re.search("Failed to index document", str(error))
        assert re.search("503", str(error))
        assert re.search("Service Unavailable", str(error))

    @set_async_streaming_bulk_results([(True, {"index": {"_id": "1"}})])
    async def test_store_counts_processed_events(self):
        await super().test_store_counts_processed_events()

    # @set_async_streaming_bulk_results([(True, {})])
    # async def test_thread_count_is_passed_to_client(self, mock_async_streaming_bulk):
    #     self.object = self._create_test_instance(config_patch={"thread_count": 42})

    #     event = LogEvent({"field": "content"}, original=b"")

    #     await self.object.setup()
    #     await self.object.store_batch([event])

    #     mock_async_streaming_bulk.assert_called_once()
    #     assert mock_async_streaming_bulk.call_args[1]["thread_count"] == 42
