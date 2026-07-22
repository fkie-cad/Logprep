# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-arguments
# pylint: disable=line-too-long

import asyncio
import json
from collections.abc import Callable, Sequence
from unittest import mock

import pytest
from opensearchpy import AsyncOpenSearch
from opensearchpy import ConnectionError as OpenSearchConnectionError
from opensearchpy import ConnectionTimeout
from opensearchpy import OpenSearchException as SearchException
from opensearchpy import RequestError, TransportError

from logprep.ng.abc.event import InputMeta, LogEvent, OutputEvent
from logprep.ng.abc.output import CriticalOutputError
from logprep.ng.connector.opensearch.output import BulkError, OpensearchOutput
from logprep.ng.util.retry import RetriesExhaustedError
from tests.unit.ng.connector.base import BaseOutputTestCase

MODULE = OpensearchOutput.__module__

CONNECTION_ERROR = OpenSearchConnectionError("N/A", "connection refused", None)


def _bulk_response(*statuses: int | dict, op_type: str = "index") -> dict:
    """Builds a bulk response with one item per given status (or raw item)."""
    return {
        "items": [
            status if isinstance(status, dict) else {op_type: {"status": status}}
            for status in statuses
        ]
    }


@pytest.mark.timeout(5)
class TestOpenSearchOutput(BaseOutputTestCase[OpensearchOutput]):
    expected_metrics = [
        "logprep_opensearch_output_number_of_bulk_requests",
        "logprep_opensearch_output_number_of_document_rejections",
        "logprep_opensearch_output_number_of_connection_failures",
        "logprep_opensearch_output_number_of_serialization_errors",
        "logprep_opensearch_output_number_of_bytes_sent",
        "logprep_opensearch_output_documents_per_bulk_request",
        "logprep_opensearch_output_send_time_per_bulk_request",
        "logprep_opensearch_output_send_time_per_batch",
        "logprep_processing_time_per_event",
        "logprep_number_of_processed_events",
        "logprep_number_of_warnings",
        "logprep_number_of_errors",
    ]

    CONFIG = {
        "type": "opensearch_output",
        "hosts": ["localhost:9200"],
        "default_index": "default_index",
        "timeout": 5000,
        "initial_backoff": 0.001,
        "max_backoff": 0.001,
    }

    @pytest.fixture
    def mock_client(self):
        with mock.patch(f"{MODULE}.AsyncOpenSearch", spec=AsyncOpenSearch) as mock_client:
            mock_client.return_value = mock_client
            mock_client.cluster = mock.MagicMock()
            mock_client.cluster.health = mock.AsyncMock()
            mock_client.cluster.health.return_value = mock.MagicMock()
            mock_client.bulk = mock.AsyncMock()
            yield mock_client

    @pytest.fixture(autouse=True)
    def autouse_central_fixtures(self, mock_client):
        yield mock_client  # return technically not required

    @pytest.fixture
    def mock_output_delivery_for_events(  # pylint: disable=arguments-differ
        self, mock_client
    ) -> Callable[[Sequence[list[bool] | Exception]], None]:
        """Adapter for the inherited base tests: each element becomes one
        bulk interaction — a response with per-item statuses, or a raised
        exception."""

        def _set_side_effect(responses: Sequence[list[bool] | Exception]):
            mock_client.bulk.side_effect = [
                (
                    response
                    if isinstance(response, Exception)
                    else _bulk_response(*(201 if ok else 400 for ok in response))
                )
                for response in responses
            ]

        return _set_side_effect

    @pytest.fixture
    def get_sent_bulk_actions(self, mock_client):
        """Reconstructs the action dicts from the NDJSON bulk request bodies."""

        def _get_actions(call_index: int = 0):
            body = mock_client.bulk.mock_calls[call_index].kwargs["body"]
            lines = [json.loads(line) for line in body.decode("utf-8").splitlines()]
            actions = []
            for meta, source in zip(lines[::2], lines[1::2]):
                op_type, meta_fields = next(iter(meta.items()))
                actions.append({"_op_type": op_type, **meta_fields, **source})
            return actions

        return _get_actions

    async def _setup_and_store(self, events: Sequence[OutputEvent]) -> None:
        await self.object.setup()
        await self.object.store(events)

    def _create_log_events(self, count: int) -> list[LogEvent]:
        return [self._create_log_event({"message": f"test message {i}"}) for i in range(count)]

    @pytest.fixture
    def tracking_mock_client(self, mock_client):
        """A mock client whose (slow, succeeding) bulk records the peak
        number of in-flight requests in :code:`mock_client.tracking`."""
        mock_client.tracking = {"in_flight": 0, "peak": 0}

        async def bulk(body):
            tracking = mock_client.tracking
            tracking["in_flight"] += 1
            tracking["peak"] = max(tracking["peak"], tracking["in_flight"])
            await asyncio.sleep(0.01)
            tracking["in_flight"] -= 1
            return _bulk_response(*[201] * (body.count(b"\n") // 2))

        mock_client.bulk = bulk
        return mock_client

    async def test_describe_returns_output(self):
        assert (
            self.object.description
            == "OpensearchOutput (Test Instance Name) - Opensearch Output: ['localhost:9200']"
        )

    async def test_store_sends_to_default_index(self, mock_client, get_sent_bulk_actions):
        mock_client.bulk.return_value = _bulk_response(201)
        event = LogEvent({"field": "content"}, original=b"", input_meta=InputMeta())

        await self._setup_and_store([event])

        assert len(event.errors) == 0
        assert get_sent_bulk_actions()[0]["_index"] == self.CONFIG.get("default_index")

    async def test_store_custom_sends_event_to_expected_index(
        self, mock_client, get_sent_bulk_actions
    ):
        mock_client.bulk.return_value = _bulk_response(201)
        data_payload = {"field": "content"}
        event = LogEvent(
            data_payload, output_target="custom_index", original=b"", input_meta=InputMeta()
        )

        await self._setup_and_store([event])

        assert len(event.errors) == 0
        assert get_sent_bulk_actions()[0] == {
            **data_payload,
            "_index": "custom_index",
            "_op_type": "index",
        }

    async def test_store_uses_configured_default_op_type(self, mock_client, get_sent_bulk_actions):
        self.object = self._create_test_instance(config_patch={"default_op_type": "create"})
        mock_client.bulk.return_value = _bulk_response(201)
        event = self._create_log_event({"field": "content"})

        await self._setup_and_store([event])

        assert get_sent_bulk_actions()[0]["_op_type"] == "create"

    async def test_store_handles_individual_errors(self, mock_client):
        mock_client.bulk.return_value = _bulk_response(400, 400)
        events = self._create_log_events(2)

        await self._setup_and_store(events)

        assert all(len(event.errors) == 1 for event in events)

    async def test_store_handles_mixed_results(self, mock_client):
        mock_client.bulk.return_value = _bulk_response(201, 400)
        events = self._create_log_events(2)

        await self._setup_and_store(events)

        assert len(events[0].errors) == 0
        assert len(events[1].errors) == 1

    async def test_store_handles_critical_client_failures(self, mock_client):
        client_exception = Exception("something unexpected")
        mock_client.bulk.side_effect = client_exception
        events = self._create_log_events(2)

        await self._setup_and_store(events)

        assert all(event.errors == [client_exception] for event in events)

    async def test_store_critical_failure_in_one_chunk_does_not_affect_others(self, mock_client):
        self.object = self._create_test_instance(config_patch={"chunk_size": 2})
        client_exception = Exception("something unexpected")
        mock_client.bulk.side_effect = [client_exception, _bulk_response(201, 201)]
        events = self._create_log_events(4)

        await self._setup_and_store(events)

        assert events[0].errors == [client_exception]
        assert events[1].errors == [client_exception]
        assert events[2].stored and events[3].stored

    async def test_store_fails_only_unserializable_events(self, mock_client, get_sent_bulk_actions):
        mock_client.bulk.return_value = _bulk_response(201)
        unserializable = self._create_log_event({"message": object()})
        serializable = self._create_log_event({"message": "test message"})

        await self._setup_and_store([unserializable, serializable])

        assert isinstance(unserializable.errors[0], BulkError)
        assert serializable.stored
        assert len(get_sent_bulk_actions()) == 1

    async def test_store_splits_batch_by_chunk_size(self, mock_client):
        self.object = self._create_test_instance(config_patch={"chunk_size": 2})
        mock_client.bulk.return_value = _bulk_response(201, 201)
        events = self._create_log_events(4)

        await self._setup_and_store(events)

        assert mock_client.bulk.await_count == 2
        assert all(event.stored for event in events)

    async def test_store_splits_batch_by_max_chunk_bytes(self, mock_client):
        self.object = self._create_test_instance(config_patch={"max_chunk_bytes": 100})
        mock_client.bulk.return_value = _bulk_response(201)
        events = [self._create_log_event({"message": "x" * 100}) for _ in range(2)]

        await self._setup_and_store(events)

        assert mock_client.bulk.await_count == 2

    async def test_store_limits_concurrent_bulk_requests(self, tracking_mock_client):
        self.object = self._create_test_instance(
            config_patch={"chunk_size": 2, "bulk_concurrency": 2}
        )
        events = self._create_log_events(8)

        await self._setup_and_store(events)

        assert all(event.stored for event in events)
        assert tracking_mock_client.tracking["peak"] == 2

    async def test_bulk_concurrency_is_shared_across_concurrent_batches(self, tracking_mock_client):
        self.object = self._create_test_instance(
            config_patch={"chunk_size": 2, "bulk_concurrency": 2}
        )
        batch_a, batch_b = self._create_log_events(4), self._create_log_events(4)

        await self.object.setup()
        await asyncio.gather(self.object.store(batch_a), self.object.store(batch_b))

        assert all(event.stored for event in batch_a + batch_b)
        assert tracking_mock_client.tracking["peak"] == 2  # instance-wide cap, not per batch

    async def test_pool_maxsize_must_cover_bulk_concurrency(self):
        with pytest.raises(ValueError, match="pool_maxsize"):
            OpensearchOutput.Config(**{**self.CONFIG, "bulk_concurrency": 16})

    async def test_store_retries_rejected_items_until_success(self, mock_client):
        mock_client.bulk.side_effect = [_bulk_response(201, 429), _bulk_response(200)]
        events = self._create_log_events(2)

        await self._setup_and_store(events)

        assert all(event.stored for event in events)
        assert mock_client.bulk.await_count == 2

    async def test_store_retries_only_the_rejected_events(self, mock_client, get_sent_bulk_actions):
        mock_client.bulk.side_effect = [_bulk_response(201, 429), _bulk_response(200)]
        events = [
            self._create_log_event({"message": "stored first try"}),
            self._create_log_event({"message": "rejected first try"}),
        ]

        await self._setup_and_store(events)

        [retried_action] = get_sent_bulk_actions(call_index=1)
        assert retried_action["message"] == "rejected first try"

    async def test_store_fails_rejected_items_when_item_retries_are_exhausted(self, mock_client):
        self.object = self._create_test_instance(config_patch={"max_bulk_item_retries": 2})
        mock_client.bulk.return_value = _bulk_response(429)
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        [error] = event.errors
        assert isinstance(error, RetriesExhaustedError)
        assert mock_client.bulk.await_count == 3  # initial attempt + 2 retries

    async def test_item_status_503_is_permanent_by_default(self, mock_client):
        mock_client.bulk.return_value = _bulk_response(503)
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        [error] = event.errors
        assert isinstance(error, BulkError)
        assert mock_client.bulk.await_count == 1

    async def test_retryable_item_statuses_are_configurable(self, mock_client):
        self.object = self._create_test_instance(
            config_patch={"retryable_item_statuses": [429, 503]}
        )
        mock_client.bulk.side_effect = [_bulk_response(503), _bulk_response(201)]
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        assert event.stored
        assert mock_client.bulk.await_count == 2

    async def test_bulk_creates_bulk_error(self, mock_client):
        mock_client.bulk.return_value = _bulk_response(
            {
                "create": {
                    "error": "Failed to index document",
                    "status": "503",
                    "exception": "Service Unavailable",
                }
            }
        )
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        [error] = event.errors
        assert isinstance(error, BulkError)
        assert "Failed to index document" in str(error)
        assert "503" in str(error)
        assert "Service Unavailable" in str(error)

    async def test_store_retries_connection_errors(self, mock_client):
        mock_client.bulk.side_effect = [CONNECTION_ERROR, CONNECTION_ERROR, _bulk_response(201)]
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        assert event.stored
        assert self.object._circuit_breaker.healthy
        assert mock_client.bulk.await_count == 3

    async def test_store_retries_connection_timeouts(self, mock_client):
        mock_client.bulk.side_effect = [
            ConnectionTimeout("TIMEOUT", "read timeout", TimeoutError()),
            _bulk_response(201),
        ]
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        assert event.stored
        assert mock_client.bulk.await_count == 2

    async def test_store_fails_events_when_connection_retries_are_exhausted(self, mock_client):
        self.object = self._create_test_instance(config_patch={"max_connection_retries": 1})
        mock_client.bulk.side_effect = CONNECTION_ERROR
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        [error] = event.errors
        assert isinstance(error, RetriesExhaustedError)
        assert mock_client.bulk.await_count == 2  # initial attempt + 1 retry
        assert not self.object._circuit_breaker.healthy

    async def test_store_retries_transport_errors_with_retryable_status(self, mock_client):
        mock_client.bulk.side_effect = [
            TransportError(503, "service_unavailable", {}),
            _bulk_response(201),
        ]
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        assert event.stored
        assert mock_client.bulk.await_count == 2

    async def test_retryable_transport_statuses_are_configurable(self, mock_client):
        self.object = self._create_test_instance(
            config_patch={"retryable_transport_statuses": [418]}
        )
        mock_client.bulk.side_effect = [
            TransportError(418, "im_a_teapot", {}),
            _bulk_response(201),
        ]
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        assert event.stored
        assert mock_client.bulk.await_count == 2

    async def test_store_does_not_retry_request_errors(self, mock_client):
        request_error = RequestError(400, "mapper_parsing_exception", {})
        mock_client.bulk.side_effect = request_error
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        assert event.errors == [request_error]
        assert mock_client.bulk.await_count == 1
        assert self.object._circuit_breaker.healthy

    async def test_store_does_not_retry_bulk_responses_violating_the_item_contract(
        self, mock_client
    ):
        mock_client.bulk.return_value = {"items": []}
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        [error] = event.errors
        assert isinstance(error, CriticalOutputError)
        assert mock_client.bulk.await_count == 1

    async def test_metrics_count_bulk_requests_documents_and_rejections(self, mock_client):
        mock_client.bulk.side_effect = [_bulk_response(201, 429), _bulk_response(200)]
        self.object.metrics.number_of_bulk_requests = 0
        self.object.metrics.number_of_document_rejections = 0
        self.object.metrics.documents_per_bulk_request = 0
        events = self._create_log_events(2)

        await self._setup_and_store(events)

        assert self.object.metrics.number_of_bulk_requests == 2
        assert self.object.metrics.number_of_document_rejections == 1
        assert self.object.metrics.documents_per_bulk_request == 2 + 1

    async def test_metrics_count_bytes_sent(self, mock_client):
        mock_client.bulk.return_value = _bulk_response(201)
        self.object.metrics.number_of_bytes_sent = 0
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        sent_body = mock_client.bulk.await_args.kwargs["body"]
        assert self.object.metrics.number_of_bytes_sent == len(sent_body)

    async def test_metrics_count_connection_failures(self, mock_client):
        mock_client.bulk.side_effect = [CONNECTION_ERROR, CONNECTION_ERROR, _bulk_response(201)]
        self.object.metrics.number_of_connection_failures = 0
        event = self._create_log_event({"message": "test message"})

        await self._setup_and_store([event])

        assert self.object.metrics.number_of_connection_failures == 2

    async def test_metrics_count_serialization_errors(self):
        self.object.metrics.number_of_serialization_errors = 0
        unserializable = self._create_log_event({"message": object()})

        await self._setup_and_store([unserializable])

        assert self.object.metrics.number_of_serialization_errors == 1

    async def test_health_returns_true_on_success(self, mock_client):
        mock_client.cluster.health.return_value = {"status": "green"}
        await self.object.setup()
        assert await self.object.health()

    @pytest.mark.parametrize("exception", [SearchException, ConnectionError])
    async def test_health_returns_false_on_failure(self, exception, mock_client):
        mock_client.cluster.health.side_effect = exception
        await self.object.setup()
        assert not await self.object.health()

    async def test_health_logs_on_failure(self, mock_client):
        mock_client.cluster.health.side_effect = SearchException
        await self.object.setup()
        with mock.patch("logging.Logger.error") as mock_error:
            assert not await self.object.health()
            mock_error.assert_called()

    async def test_health_counts_metrics_on_failure(self, mock_client):
        self.object.metrics.number_of_errors = 0
        mock_client.cluster.health.side_effect = SearchException
        await self.object.setup()
        assert not await self.object.health()
        assert self.object.metrics.number_of_errors == 1

    async def test_health_returns_false_on_cluster_status_not_green(self, mock_client):
        mock_client.cluster.health.return_value = {"status": "yellow"}
        await self.object.setup()
        assert not await self.object.health()

    async def test_health_returns_false_while_connection_is_degraded(self, mock_client):
        await self.object.setup()
        self.object._circuit_breaker._failures = 2
        assert not await self.object.health()
        mock_client.cluster.health.assert_not_called()
