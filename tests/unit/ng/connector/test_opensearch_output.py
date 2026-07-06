# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-arguments
# pylint: disable=line-too-long

import json
from collections.abc import Callable, Sequence
from contextlib import nullcontext
from functools import partial
from unittest import mock

import pytest
from opensearchpy import AsyncOpenSearch
from opensearchpy import OpenSearchException as SearchException
from opensearchpy import helpers

from logprep.ng.abc.event import InputMeta, LogEvent
from logprep.ng.connector.opensearch.output import BulkError, OpensearchOutput
from tests.unit.ng.connector.base import BaseOutputTestCase

helpers.parallel_bulk = mock.MagicMock()

MODULE = OpensearchOutput.__module__


class TestOpenSearchOutput(BaseOutputTestCase[OpensearchOutput]):
    CONFIG = {
        "type": "opensearch_output",
        "hosts": ["localhost:9200"],
        "default_index": "default_index",
        "message_backlog_size": 1,
        "timeout": 5000,
    }

    @pytest.fixture
    def mock_client(self):
        with mock.patch(f"{MODULE}.AsyncOpenSearch", spec=AsyncOpenSearch) as mock_client:
            mock_client.return_value = mock_client
            mock_client.cluster = mock.MagicMock()
            mock_client.cluster.health = mock.AsyncMock()
            mock_client.cluster.health.return_value = mock.MagicMock()
            mock_client.transport = mock.MagicMock()
            mock_client.transport.serializer = mock.MagicMock()
            mock_client.transport.serializer.dumps = json.dumps
            yield mock_client

    @pytest.fixture
    def mock_async_streaming_bulk(self):
        with mock.patch(
            f"{MODULE}.helpers.async_streaming_bulk",
            wraps=helpers.async_streaming_bulk,
        ) as mock_helper:
            yield mock_helper

    @pytest.fixture
    def mock_output_delivery_for_events(  # pylint: disable=arguments-differ
        self, mock_async_streaming_bulk
    ) -> Callable[[Sequence[bool | Exception | tuple[bool | Exception, dict]]], None]:
        """Concrete implementation ensures the given events are delivered successfully"""

        def _set_side_effect(responses: Sequence[bool | Exception | tuple[bool | Exception, dict]]):
            async def gen_return_values(helper_mock, *_, **kwargs):
                actions = list(kwargs["actions"])

                # we have exhausted the actions generator, let's restore it in the call record
                helper_mock.mock_calls[-1].kwargs["actions"] = actions  # (a for a in actions)

                for i, (action, response) in enumerate(zip(actions, responses)):
                    if isinstance(response, tuple):
                        response_ok, response_data = response
                    else:
                        response_ok, response_data = response, None
                    if isinstance(response_ok, Exception):
                        raise response_ok
                    yield response_ok, (
                        response_data
                        if response_data is not None
                        else {action["_op_type"]: {"_index": action["_index"], "_id": i}}
                    )

            mock_async_streaming_bulk.side_effect = partial(
                gen_return_values, mock_async_streaming_bulk
            )

        return _set_side_effect

    @pytest.fixture(autouse=True)
    def autouse_central_fixtures(self, mock_client, mock_async_streaming_bulk):
        yield mock_client, mock_async_streaming_bulk  # return technically not required

    @pytest.fixture
    def mock_async_streaming_bulk_get_actions(self, mock_async_streaming_bulk):
        def _get_actions(call_index: int = 0):
            return list(mock_async_streaming_bulk.mock_calls[call_index].kwargs["actions"])

        return _get_actions

    # ==========================================================================

    async def test_describe_returns_output(self):
        assert (
            self.object.description
            == "OpensearchOutput (Test Instance Name) - Opensearch Output: ['localhost:9200']"
        )

    async def test_store_sends_to_default_index(
        self, mock_output_delivery_for_events, mock_async_streaming_bulk_get_actions
    ):
        event = LogEvent({"field": "content"}, original=b"", input_meta=InputMeta())

        await self.object.setup()
        mock_output_delivery_for_events([True])
        await self.object.store([event])

        assert len(event.errors) == 0
        assert mock_async_streaming_bulk_get_actions()[0]["_index"] == self.CONFIG.get(
            "default_index"
        )

    async def test_store_custom_sends_event_to_expected_index(
        self, mock_output_delivery_for_events, mock_async_streaming_bulk_get_actions
    ):
        data_payload = {"field": "content"}
        event = LogEvent(
            data_payload, output_target="custom_index", original=b"", input_meta=InputMeta()
        )

        await self.object.setup()
        mock_output_delivery_for_events([True])
        await self.object.store([event])

        assert len(event.errors) == 0
        assert mock_async_streaming_bulk_get_actions()[0] == {
            **data_payload,
            "_index": "custom_index",
            "_op_type": "index",
        }

    async def test_store_handles_individual_errors(self, mock_output_delivery_for_events):
        event1 = self._create_log_event({"message": "test message"}, output_target=None)
        event2 = self._create_log_event({"message": "test message"}, output_target="custom")
        await self.object.setup()
        mock_output_delivery_for_events([False, False])
        await self.object.store([event1, event2])
        assert len(event1.errors) == 1
        assert len(event2.errors) == 1

    async def test_store_handles_immediate_helper_failures(self, mock_async_streaming_bulk):
        helper_exception = Exception("something unexpected")
        mock_async_streaming_bulk.side_effect = helper_exception
        event1 = self._create_log_event({"message": "test message"}, output_target=None)
        event2 = self._create_log_event({"message": "test message"}, output_target="custom")
        await self.object.setup()
        await self.object.store([event1, event2])
        assert event1.errors == [helper_exception]
        assert event2.errors == [helper_exception]

    async def test_store_handles_intermediate_helper_failurs(self, mock_output_delivery_for_events):
        event1 = self._create_log_event({"message": "test message"}, output_target=None)
        event2 = self._create_log_event({"message": "test message"}, output_target="custom")
        await self.object.setup()
        mock_output_delivery_for_events([True, Exception("something unexpected")])
        await self.object.store([event1, event2])
        assert event1.stored
        assert "something unexpected" == str(event2.errors[0])

    async def test_store_handles_mixed_results(self, mock_output_delivery_for_events):
        event1 = self._create_log_event({"message": "test message"})
        event2 = self._create_log_event({"message": "test message"})
        await self.object.setup()
        mock_output_delivery_for_events([True, False])
        await self.object.store([event1, event2])
        assert len(event1.errors) == 0
        assert len(event2.errors) == 1

    @mock.patch("inspect.getmembers", return_value=[("mock_prop", lambda: None)])
    async def test_setup_populates_cached_properties(self, mock_getmembers):
        await self.object.setup()
        mock_getmembers.assert_called_with(self.object)

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

    async def test_bulk_creates_bulk_error(self, mock_output_delivery_for_events):
        event = LogEvent({"message": "test message"}, original=b"", input_meta=InputMeta())
        await self.object.setup()
        mock_output_delivery_for_events(
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
        await self.object.store([event])
        [error] = event.errors
        assert isinstance(error, BulkError)
        assert "Failed to index document" in str(error)
        assert "503" in str(error)
        assert "Service Unavailable" in str(error)

    @pytest.mark.parametrize(
        "status_codes, client_kwargs, maybe_expect_exception",
        [
            pytest.param(
                [
                    (True, (200,)),
                    (True, (200,)),
                    (True, (200,)),
                    (True, (200,)),
                ],
                {"chunk_size": 2, "max_retries": 0},
                nullcontext(),
                id="4x-successful-on-first-try",
            ),
            pytest.param(
                [
                    (False, (500,)),
                    (True, (200,)),
                    (True, (200,)),
                    (False, (500,)),
                ],
                {"chunk_size": 2, "max_retries": 0},
                nullcontext(),
                id="1x-final-fail-per-chunk",
            ),
            pytest.param(
                [
                    (True, (429, 200)),
                    (True, (200,)),
                    (True, (200,)),
                    (True, (429, 200)),
                ],
                {"chunk_size": 2, "max_retries": 1},
                pytest.raises(AssertionError, match="ordering broken"),
                id="retries-break-ordering",
            ),
        ],
    )
    async def test_async_streaming_bulk_maintains_order(
        self, mock_client, status_codes, client_kwargs, maybe_expect_exception
    ):
        item_id_to_status_code_seq = {i: list(codes) for i, (_, codes) in enumerate(status_codes)}
        item_id_to_expected_success = {i: ok for i, (ok, _) in enumerate(status_codes)}

        async def _bulk(body: str):
            # body is a jsonl string like:
            #   { "index": {} }\n
            #   { "id": X     }\n <- first item id
            #   { "index": {} }\n
            #   { "id": X + 1 }\n <- second item id ...
            items = [json.loads(entry) for entry in body.splitlines()][1::2]
            item_ids = [action["id"] for action in items]
            return {
                "items": [
                    {
                        "index": {
                            "status": item_id_to_status_code_seq[item_id].pop(0),
                            "id": item_id,
                        }
                    }
                    for item_id in item_ids
                ]
            }

        mock_client.bulk = mock.AsyncMock(wraps=_bulk)

        actions = ({"_op_type": "index", "id": i} for i in range(len(status_codes)))

        last_index = None

        with maybe_expect_exception:
            async for success, item in helpers.async_streaming_bulk(
                mock_client,
                actions,
                max_backoff=0,  # disable sleep when retrying
                max_chunk_bytes=9999,  # no limit
                raise_on_error=False,
                raise_on_exception=False,
                **client_kwargs,
            ):
                item_id = item["index"]["id"]
                assert success is item_id_to_expected_success[item_id]
                assert last_index is None or last_index < item_id, "ordering broken"
                last_index = item_id
