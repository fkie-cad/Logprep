"""
OpensearchOutput
================

This section contains the connection settings for Opensearch, the default index, the error index
and a buffer size. Documents are sent in batches to Opensearch to reduce the amount of times
connections are created.

The documents desired index :code:`_index` can be set using :code:`event.output_target` (or
:code:`_index` as data field).
Data fields prefixed with an underscore (like :code:`_index`, :code:`_op_type`) will be fed to
Opensearch as-is, meaning these will be interpreted as metadata by Opensearch.
This functionality might change in the future to avoid unintended mixup between pure data and
Opensearch metadata.
If you want to send documents to data streams, you have to set the field :code:`_op_type: create` in
the document.

Sending the data involves different layers:
- Chunking: split the batch into smaller chunks and process concurrently
- Item-level reject: send a chunk and retry rejected items until all events are stored or failed
- Circuit breaker: retry transient connection errors and limit concurrency
- Opensearch client: manage connection pool and retry with another connection on errors

Retry behavior can be configured in the following ways:
- Item-level reject:
  Retries rejected items for a configurable number of times
  (:code:`max_bulk_item_retries`, indefinitely by default).
  A retry is only attempted if the item status is deemed retryable
  (:code:`retryable_item_statuses`, by default 429).
  Other non-success statuses will lead to corresponding event failures.
- Circuit breaker:
  Retries connection-level failures for a configurable number of times
  (:code:`max_connection_retries`, indefinitely by default).
  This kind of failure includes retryable request-level status as of Opensearch,
  timeouts and other connection errors.
  The circuit breaker opens (=breaks) the circuit on failures and only allows for
  single probes at a time until the downstream system is deemed healthy again.
  The breaker also limits maximum concurrency to :code:`bulk_concurrency`.
  Depending on the nature of failure, retries on this level might lead to duplicates.
- Opensearch client:
  Manages a pool of at maximum :code:`pool_maxsize` connections which will be used
  to handle concurrent connections but also fail-over and retries in case of errors.
  While timeouts are handled by the circuit breaker, connection errors and other
  transport-level status codes (like 502, 503 and 504) get retried a maximum of
  :code:`max_client_retries` times.

Circuit breaker and opensearch client are instance-wide.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    output:
      myopensearch_output:
        type: opensearch_output
        hosts:
            - 127.0.0.1:9200
        default_index: default_index
        error_index: error_index
        timeout: 10000
        user:
        secret:
        ca_cert: /path/to/cert.crt
        max_bulk_item_retries:          # retry rejected items (429) forever
        max_connection_retries:         # unbounded; bound it to limit duplicates
        initial_backoff: 2
        max_backoff: 600
        bulk_concurrency: 4             # bulk requests in flight across the output
"""

import asyncio
import logging
import ssl
import typing
from collections.abc import Iterator, Sequence
from functools import cached_property, partial
from typing import Any

from attrs import define, field, validators
from opensearchpy import (
    AsyncOpenSearch,
)
from opensearchpy import ConnectionError as OpenSearchConnectionError
from opensearchpy import (
    OpenSearchException,
    SerializationError,
    TransportError,
)
from opensearchpy.helpers.actions import expand_action
from opensearchpy.serializer import JSONSerializer

from logprep.abc.exceptions import LogprepException
from logprep.metrics.metrics import CounterMetric, HistogramMetric, Metric
from logprep.ng.abc.event import OutputEvent
from logprep.ng.abc.output import CriticalOutputError, Output
from logprep.ng.util.retry import Backoff, BlockingCircuitBreaker, RetriesExhaustedError

logger = logging.getLogger("OpenSearchOutput")


class BulkError(LogprepException):
    """Exception created when a bulk operation fails in Opensearch."""

    def __init__(
        self,
        message: str,
        status: int | str | None = None,
        exception: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.exception = exception

    def __str__(self) -> str:
        return f"BulkError: {self.message}, status_code: {self.status}, exception: {self.exception}"


class MsgspecSerializer(JSONSerializer):
    """Plugs Logprep's msgspec JSON codec into the opensearch-py client."""

    def __init__(self, encoder, decoder, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._encoder = encoder
        self._decoder = decoder

    def dumps(self, data):
        if isinstance(data, (str, bytes)):
            return data
        try:
            return self._encoder.encode(data).decode("utf-8")
        except (ValueError, TypeError) as error:
            raise SerializationError(data) from error

    def loads(self, s):
        return self._decoder.decode(s)


@define
class _Chunk:
    """One bulk request worth of events with their pre-serialized payload lines (parallel lists)."""

    events: list[OutputEvent]
    payloads: list[bytes]

    @property
    def is_resolved(self) -> bool:
        """Whether every event of this chunk is stored or failed."""
        return not self.events

    @property
    def payload(self) -> bytes:
        """The bulk request body for the currently unresolved events."""
        return b"".join(self.payloads)

    def shrink_to(self, indices: list[int]) -> None:
        """Keeps only the events at the given indices for the next attempt."""
        self.events = [self.events[i] for i in indices]
        self.payloads = [self.payloads[i] for i in indices]

    def fail_remaining(self, error: Exception) -> None:
        """Marks all not yet resolved events of this chunk as failed."""
        for event in self.events:
            if not event.stored and not event.is_failed():
                event.mark_failed(error)
        self.events, self.payloads = [], []


def _validate_pool_covers_concurrency(instance: Any, _: Any, value: int) -> None:
    if value < instance.bulk_concurrency:
        raise ValueError(
            f"pool_maxsize ({value}) must be >= bulk_concurrency ({instance.bulk_concurrency})"
        )


class OpensearchOutput(Output):
    """An OpenSearch output connector."""

    @define(kw_only=True)
    class Metrics(Output.Metrics):
        """Tracks statistics about the OpensearchOutput"""

        number_of_bulk_requests: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of bulk requests sent to Opensearch, including retries",
                name="opensearch_output_number_of_bulk_requests",
            )
        )
        """Number of bulk requests sent to Opensearch, including retries"""
        number_of_document_rejections: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of documents rejected with a retryable status (e.g. 429)",
                name="opensearch_output_number_of_document_rejections",
            )
        )
        """Number of documents rejected with a retryable status (e.g. 429)"""
        number_of_connection_failures: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of transient connection failures",
                name="opensearch_output_number_of_connection_failures",
            )
        )
        """Number of transient connection failures"""
        number_of_serialization_errors: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of events that could not be serialized",
                name="opensearch_output_number_of_serialization_errors",
            )
        )
        """Number of events that could not be serialized"""
        number_of_bytes_sent: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Total payload bytes sent in bulk requests, including retries",
                name="opensearch_output_number_of_bytes_sent",
            )
        )
        """Total payload bytes sent in bulk requests, including retries"""
        documents_per_bulk_request: HistogramMetric = field(
            factory=lambda: HistogramMetric(
                description="Number of documents per sent bulk request",
                name="opensearch_output_documents_per_bulk_request",
            )
        )
        """Number of documents per sent bulk request"""
        send_time_per_bulk_request: HistogramMetric = field(
            factory=lambda: HistogramMetric(
                description="Time in seconds for one bulk request",
                name="opensearch_output_send_time_per_bulk_request",
            )
        )
        """Time in seconds for one bulk request"""
        send_time_per_batch: HistogramMetric = field(
            factory=lambda: HistogramMetric(
                description="Time in seconds to store one batch of events",
                name="opensearch_output_send_time_per_batch",
            )
        )
        """Time in seconds to store one batch of events"""

    @define(kw_only=True, slots=False)
    class Config(Output.Config):
        """Opensearch Output Config

        .. security-best-practice::
           :title: Output Connectors - OpensearchOutput

           It is suggested to enable a secure message transfer by setting :code:`user`,
           :code:`secret` and a valid :code:`ca_cert`.
        """

        hosts: list[str] = field(
            validator=validators.deep_iterable(
                member_validator=validators.instance_of((str, type(None))),
                iterable_validator=validators.instance_of(list),
            ),
            factory=list,
        )
        """Addresses of opensearch/opensearch servers. Can be a list of hosts or one single host
        in the format HOST:PORT without specifying a schema. The schema is set automatically to
        https if a certificate is being used."""

        default_index: str = field(validator=validators.instance_of(str))
        """Default index to write to if no index was set in the document or the document could not
        be indexed. The document will be transformed into a string to prevent rejections by the
        default index."""

        timeout: int = field(validator=validators.instance_of(int), default=500)
        """(Optional) Timeout for the connection (default is 500ms)."""

        user: str | None = field(validator=validators.instance_of(str), default="")
        """(Optional) User used for authentication."""

        secret: str | None = field(validator=validators.instance_of(str), default="")
        """(Optional) Secret used for authentication."""

        ca_cert: str | None = field(validator=validators.instance_of(str), default="")
        """(Optional) Path to a SSL ca certificate to verify the ssl context."""

        chunk_size: int = field(
            default=500, validator=[validators.instance_of(int), validators.gt(1)]
        )
        """Chunk size to use for bulk requests."""

        max_chunk_bytes: int = field(
            default=100 * 1024 * 1024,
            validator=[validators.instance_of(int), validators.gt(1)],
        )
        """Max chunk size to use for bulk requests. The default is 100MB."""

        max_client_retries: int = field(
            default=3, validator=[validators.instance_of(int), validators.gt(0)]
        )
        """Max retries the transport layer performs *per request*, immediately
        and without backoff: node failover on connection errors and
        request-level 502/503/504 responses, marking failing nodes dead in
        the connection pool. Failures that survive this budget continue in
        the connector's circuit breaker (:code:`max_connection_retries`, with
        backoff); item-level rejections are invisible to the transport and
        governed by :code:`max_bulk_item_retries`. Default is 3."""

        max_bulk_item_retries: int | None = field(
            default=None,
            validator=validators.optional([validators.instance_of(int), validators.ge(0)]),
        )
        """Max retries for bulk items rejected with a status listed in
        :code:`retryable_item_statuses` (e.g. 429). Such rejections are
        authoritative "not stored" responses, so retrying them is
        duplicate-free. :code:`None` (the default) retries indefinitely,
        stalling the batch and thereby applying backpressure towards the
        input. On exhaustion the affected events are marked as failed."""

        max_connection_retries: int | None = field(
            default=None,
            validator=validators.optional([validators.instance_of(int), validators.ge(0)]),
        )
        """Max consecutive transport-level failures (timeout, connection
        reset) across the whole output before affected events are marked as
        failed. Transport failures are coordinated instance-wide: one request
        probes the broken connection with backoff while all others wait.
        :code:`None` (the default) retries indefinitely, stalling the batch
        and thereby applying backpressure towards the input. The outcome of a
        transport failure is unknown, so every retry may produce duplicates;
        set a bound to limit duplicates at the price of failing events."""

        initial_backoff: float = field(
            default=2.0, validator=[validators.instance_of((int, float)), validators.gt(0)]
        )
        """Backoff in seconds before the first retry (item retries and
        connection probes alike); doubles per retry up to :code:`max_backoff`,
        with equal jitter applied. Default is 2."""

        max_backoff: float = field(
            default=600.0, validator=[validators.instance_of((int, float)), validators.gt(0)]
        )
        """Upper bound in seconds for the retry backoff. Default is 600."""

        bulk_concurrency: int = field(
            default=4, validator=[validators.instance_of(int), validators.ge(1)]
        )
        """Number of bulk requests in flight concurrently across the whole
        output (enforced by the circuit breaker, shared by concurrently
        processed batches). Higher values increase throughput at the cost of
        more parallel load on the cluster. Must not exceed
        :code:`pool_maxsize`. Default is 4."""

        pool_maxsize: int = field(
            default=10,
            validator=[
                validators.instance_of(int),
                validators.ge(1),
                _validate_pool_covers_concurrency,
            ],
        )
        """Connection pool size of the async transport. Must be at least
        :code:`bulk_concurrency` so that concurrent chunks never starve on
        connections. Default is 10."""

        retryable_item_statuses: list[int] = field(
            factory=lambda: [429],
            validator=validators.deep_iterable(
                member_validator=validators.instance_of(int),
                iterable_validator=validators.instance_of(list),
            ),
        )
        """Item-level response statuses that are retried under
        :code:`max_bulk_item_retries`. All other non-2xx item statuses are
        treated as permanent failures. Default is [429], matching the
        client's own bulk-retry policy. 503 (unavailable shards) can be
        added: retrying it is duplicate-free, but a persistently red index
        will stall an unlimited budget."""

        retryable_transport_statuses: list[int] = field(
            factory=lambda: [502, 503, 504],
            validator=validators.deep_iterable(
                member_validator=validators.instance_of(int),
                iterable_validator=validators.instance_of(list),
            ),
        )
        """Transport-level response statuses that are retried under
        :code:`max_client_retries` (opensearch client) and
        :code:`max_connection_retries` (circuit breaker). Default is
        [502, 503, 504], matching the client's own transport retry policy
        (:code:`retry_on_status`)."""

        desired_cluster_status: list = field(
            factory=lambda: ["green"], validator=validators.instance_of(list)
        )
        """Desired cluster status for health check as list of strings. Default is ["green"]"""

        default_op_type: str = field(
            default="index",
            validator=[
                validators.instance_of(str),
                validators.in_(["create", "index"]),
            ],
        )
        """Default op_type for indexing documents. Default is 'index',
        Consider using 'create' for data streams or to prevent overwriting existing documents."""

    __slots__ = ("_search_context",)

    @property
    def _metrics(self) -> "OpensearchOutput.Metrics":
        """Provides the properly typed metrics object"""
        return typing.cast(OpensearchOutput.Metrics, self.metrics)

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast(OpensearchOutput.Config, self._config)

    @property
    def schema(self) -> str:
        """Returns the schema. `https` if ssl config is set, else `http`"""
        return "https" if self.config.ca_cert else "http"

    @property
    def http_auth(self) -> tuple[str, str] | None:
        """Returns the credentials the credentials in format (user, secret) or None"""
        if self.config.user and self.config.secret:
            return (self.config.user, self.config.secret)
        return None

    @cached_property
    def _default_action_config(self) -> dict[str, str]:
        return {
            "_index": self.config.default_index,
            "_op_type": self.config.default_op_type,
        }

    @cached_property
    def _serializer(self) -> MsgspecSerializer:
        return MsgspecSerializer(self._encoder, self._decoder)

    @cached_property
    def _backoff(self) -> Backoff:
        return Backoff(
            initial=self.config.initial_backoff,
            maximum=self.config.max_backoff,
        )

    @cached_property
    def _circuit_breaker(self) -> BlockingCircuitBreaker:
        return BlockingCircuitBreaker(
            backoff=self._backoff,
            max_retries=self.config.max_connection_retries,
            is_transient=self._is_transient_connection_error,
            on_transient_failure=self._count_connection_failure,
            concurrency=self.config.bulk_concurrency,
        )

    def _is_transient_connection_error(self, error: Exception) -> bool:
        """Transport failures with unknown outcome: connection errors including
        timeouts, and retryable request-level statuses."""
        if isinstance(error, OpenSearchConnectionError):  # includes ConnectionTimeout
            return True
        if isinstance(error, TransportError):
            return error.status_code in self.config.retryable_transport_statuses
        return isinstance(error, OSError)  # includes TimeoutError

    def _count_connection_failure(self, _: Exception) -> None:
        self._metrics.number_of_connection_failures += 1

    def _describe(self) -> str:
        """Get name of Opensearch endpoint with the host."""
        return f"{Output._describe(self)} - Opensearch Output: {self.config.hosts}"

    def _create_ssl_context(self) -> ssl.SSLContext | None:
        """Returns the ssl context"""
        if self.config.ca_cert:
            return ssl.create_default_context(cafile=self.config.ca_cert)
        return None

    async def setup(self):
        self._search_context = AsyncOpenSearch(
            self.config.hosts,
            scheme=self.schema,
            http_auth=self.http_auth,
            ssl_context=self._create_ssl_context(),
            verify_certs=True,
            timeout=self.config.timeout,
            serializer=self._serializer,
            max_client_retries=self.config.max_client_retries,
            retry_on_status=self.config.retryable_transport_statuses,
            pool_maxsize=self.config.pool_maxsize,
        )
        return await super().setup()

    def _serialize(self, event: OutputEvent) -> bytes:
        """
        Serializes one event into its bulk request lines.\n
        Raises :code:`SerializationError` for any unserializable event.
        """
        raw_action = {
            **self._default_action_config,
            **({"_index": event.output_target} if event.output_target is not None else {}),
            **event.data,
            # TODO disallow overwriting arbitrary os metadata (_ prefixed) in the future
        }
        try:
            meta, source = expand_action(raw_action)
            lines = [self._encoder.encode(meta)]
            if source is not None:
                lines.append(self._encoder.encode(source))
        except (ValueError, TypeError) as error:
            raise SerializationError(raw_action) from error
        return b"\n".join(lines) + b"\n"

    def _chunks(self, events: Sequence[OutputEvent]) -> Iterator[_Chunk]:
        """
        Serializes the batch into chunks bounded by :code:`chunk_size` and :code:`max_chunk_bytes`.
        Serialization errors result in immediate event failures.
        Oversized events get their own chunk.
        """
        chunk_events: list[OutputEvent] = []
        chunk_payloads: list[bytes] = []
        chunk_bytes = 0
        for event in events:
            try:
                payload = self._serialize(event)
            except SerializationError as error:
                logger.info("failed to serialize event %s", event, exc_info=True)
                self._metrics.number_of_serialization_errors += 1
                event.mark_failed(
                    BulkError(message=f"failed to serialize event: {error}", exception=str(error))
                )
                continue
            size = len(payload)
            if chunk_events and (
                len(chunk_events) >= self.config.chunk_size
                or chunk_bytes + size > self.config.max_chunk_bytes
            ):
                yield _Chunk(chunk_events, chunk_payloads)
                chunk_events, chunk_payloads, chunk_bytes = [], [], 0
            chunk_events.append(event)
            chunk_payloads.append(payload)
            chunk_bytes += size
        if chunk_events:
            yield _Chunk(chunk_events, chunk_payloads)

    def _resolve_response_items(self, chunk: _Chunk, response: dict[str, Any]) -> bool:
        """
        Handles the bulk response for each item individually:
        - Item stored successfully -> mark event stored and remove from chunk
        - Item failed with retryable error -> keep in chunk for next attempt
        - Item failed otherwise -> mark event failed and remove from chunk
        """
        response_items = response.get("items", [])
        if len(response_items) != len(chunk.events):
            raise CriticalOutputError.from_message(
                self,
                f"bulk response contained {len(response_items)} items "
                f"for {len(chunk.events)} actions",
            )

        retry_indices: list[int] = []
        for i, (event, response_item) in enumerate(zip(chunk.events, response_items)):
            # structure of response_item is always `{ $op_type: { ... } }`
            if not (isinstance(response_item, dict) and len(response_item) == 1):
                raise CriticalOutputError.from_message(
                    self, f"unexpected structure of response item: {response_item}"
                )
            op_type, result = typing.cast(
                tuple[str, dict[str, Any]], next(iter(response_item.items()))
            )
            status = result.get("status", 500)
            if isinstance(status, int) and 200 <= status < 300:
                event.stored = True
            elif status in self.config.retryable_item_statuses:
                retry_indices.append(i)
            else:
                logger.debug("event failed to send: %s", response_item)
                event.mark_failed(
                    BulkError(
                        message=result.get("error", f"Failed to `{op_type}` document"),
                        exception=result.get("exception"),
                        status=status,
                    )
                )
        if retry_indices:
            self._metrics.number_of_document_rejections += len(retry_indices)
        chunk.shrink_to(retry_indices)
        return chunk.is_resolved

    @Metric.measure_time_async(metric_name="send_time_per_bulk_request")
    async def _send(self, chunk: _Chunk) -> dict[str, Any]:
        """One bulk network request; counts requests, documents and bytes."""
        payload = chunk.payload
        self._metrics.number_of_bulk_requests += 1
        self._metrics.documents_per_bulk_request += len(chunk.events)
        self._metrics.number_of_bytes_sent += len(payload)
        return await self._search_context.bulk(body=payload)

    async def _resolve_chunk(self, chunk: _Chunk) -> None:
        """
        Sends chunk repeatedly for retryable item errors until all events are stored or failed.
        The circuit breaker handles transient connectivity issues and limits concurrency.
        """
        try:
            attempt = 0
            async for attempt in self._backoff.attempts(self.config.max_bulk_item_retries):
                response = await self._circuit_breaker.call(partial(self._send, chunk))

                if self._resolve_response_items(chunk, response):
                    return

                logger.info("%d events were rejected (attempt %d)", len(chunk.events), attempt)
            raise RetriesExhaustedError(f"bulk item retries exhausted after {attempt} attempts")
        except RetriesExhaustedError as error:
            chunk.fail_remaining(error)
        except Exception as error:
            logger.error("critical failure while sending bulk chunk", exc_info=True)
            chunk.fail_remaining(error)

    @Metric.measure_time_async(metric_name="processing_time_per_event")
    @Metric.measure_time_async(metric_name="send_time_per_batch")
    async def _store(self, events: Sequence[OutputEvent]) -> None:
        logger.debug("Flushing %d documents to opensearch", len(events))
        await asyncio.gather(*(self._resolve_chunk(chunk) for chunk in self._chunks(events)))

    async def health(self) -> bool:  # type: ignore[override]
        """Check the health of the component. Shortcuts on unhealthy cluster breaker."""
        if not self._circuit_breaker.healthy:
            return False
        try:
            resp = await self._search_context.cluster.health(
                params={"timeout": self.config.health_timeout}
            )
        except (OpenSearchException, ConnectionError) as error:
            logger.error("Health check failed: %s", error)
            self._metrics.number_of_errors += 1
            return False
        return (await super().health()) and resp.get("status") in self.config.desired_cluster_status

    async def shut_down(self):
        await self._search_context.close()
        await super().shut_down()
