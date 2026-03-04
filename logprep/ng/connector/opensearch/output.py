"""
OpensearchOutput
================

This section contains the connection settings for Opensearch, the default
index, the error index and a buffer size. Documents are sent in batches to Opensearch to reduce
the amount of times connections are created.

The documents desired index is the field :code:`_index` in the document. It is deleted afterwards.
If you want to send documents to data streams, you have to set the field :code:`_op_type: create` in
the document.

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
        message_backlog_size: 10000
        timeout: 10000
        max_retries:
        user:
        secret:
        ca_cert: /path/to/cert.crt
"""

import asyncio
import json
import logging
import ssl
import typing
from functools import cached_property
from typing import List, Optional

from attrs import define, field, validators
from opensearchpy import (
    AsyncOpenSearch,
    OpenSearchException,
    SerializationError,
    helpers,
)
from opensearchpy.serializer import JSONSerializer

from logprep.abc.exceptions import LogprepException
from logprep.metrics.metrics import Metric
from logprep.ng.abc.event import Event
from logprep.ng.abc.output import Output
from logprep.ng.event.event_state import EventStateType

logger = logging.getLogger("OpenSearchOutput")


class BulkError(LogprepException):
    """Exception created when a bulk operation fails in Opensearch."""

    def __init__(
        self,
        message: str,
        status: str | None = None,
        exception: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.exception = exception

    def __str__(self) -> str:
        return f"BulkError: {self.message}, status_code: {self.status}, exception: {self.exception}"


class MSGPECSerializer(JSONSerializer):
    """A MSGPEC serializer"""

    def __init__(self, output_connector: Output, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._encoder = output_connector._encoder
        self._decoder = output_connector._decoder

    def dumps(self, data):
        # don't serialize strings
        if isinstance(data, str):
            return data
        try:
            return self._encoder.encode(data).decode("utf-8")
        except (ValueError, TypeError) as e:
            raise SerializationError(data, e)

    def loads(self, s):
        return self._decoder.decode(s)


class OpensearchOutput(Output):
    """An OpenSearch output connector."""

    @define(kw_only=True, slots=False)
    class Config(Output.Config):
        """Opensearch Output Config

        .. security-best-practice::
           :title: Output Connectors - OpensearchOutput

           It is suggested to enable a secure message transfer by setting :code:`user`,
           :code:`secret` and a valid :code:`ca_cert`.
        """

        hosts: List[str] = field(
            validator=validators.deep_iterable(
                member_validator=validators.instance_of((str, type(None))),
                iterable_validator=validators.instance_of(list),
            ),
            default=[],
        )
        """Addresses of opensearch/opensearch servers. Can be a list of hosts or one single host
        in the format HOST:PORT without specifying a schema. The schema is set automatically to
        https if a certificate is being used."""
        default_index: str = field(validator=validators.instance_of(str))
        """Default index to write to if no index was set in the document or the document could not
        be indexed. The document will be transformed into a string to prevent rejections by the
        default index."""
        message_backlog_size: int = field(validator=validators.instance_of(int))
        """Amount of documents to store before sending them."""
        timeout: int = field(validator=validators.instance_of(int), default=500)
        """(Optional) Timeout for the connection (default is 500ms)."""
        user: Optional[str] = field(validator=validators.instance_of(str), default="")
        """(Optional) User used for authentication."""
        secret: Optional[str] = field(validator=validators.instance_of(str), default="")
        """(Optional) Secret used for authentication."""
        ca_cert: Optional[str] = field(validator=validators.instance_of(str), default="")
        """(Optional) Path to a SSL ca certificate to verify the ssl context."""
        flush_timeout: Optional[int] = field(validator=validators.instance_of(int), default=60)
        """(Optional) Timeout after :code:`message_backlog` is flushed if
        :code:`message_backlog_size` is not reached."""
        thread_count: int = field(
            default=4, validator=(validators.instance_of(int), validators.gt(1))
        )
        """Number of threads to use for bulk requests."""
        queue_size: int = field(
            default=4, validator=(validators.instance_of(int), validators.gt(1))
        )
        """Number of queue size to use for bulk requests."""
        chunk_size: int = field(
            default=500, validator=(validators.instance_of(int), validators.gt(1))
        )
        """Chunk size to use for bulk requests."""
        max_chunk_bytes: int = field(
            default=100 * 1024 * 1024, validator=(validators.instance_of(int), validators.gt(1))
        )
        """Max chunk size to use for bulk requests. The default is 100MB."""
        max_retries: int = field(
            default=3, validator=(validators.instance_of(int), validators.gt(0))
        )
        """Max retries for all requests. Default is 3."""
        desired_cluster_status: list = field(
            default=["green"], validator=validators.instance_of(list)
        )
        """Desired cluster status for health check as list of strings. Default is ["green"]"""
        default_op_type: str = field(
            default="index",
            validator=(validators.instance_of(str), validators.in_(["create", "index"])),
        )
        """Default op_type for indexing documents. Default is 'index',
        Consider using 'create' for data streams or to prevent overwriting existing documents."""

    __slots__ = ("_message_backlog", "_flush_task")

    _message_backlog: list[Event]
    """List of messages to be sent to Opensearch."""

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(OpensearchOutput.Config, self._config)

    @cached_property
    def ssl_context(self) -> ssl.SSLContext | None:
        """Returns the ssl context

        Returns
        -------
        SSLContext
            The ssl context
        """
        return (
            ssl.create_default_context(cafile=self.config.ca_cert) if self.config.ca_cert else None
        )

    @property
    def schema(self) -> str:
        """Returns the schema. `https` if ssl config is set, else `http`

        Returns
        -------
        str
            the schema
        """
        return "https" if self.config.ca_cert else "http"

    @property
    def http_auth(self) -> tuple | None:
        """Returns the credentials

        Returns
        -------
        tuple
            the credentials in format (user, secret)
        """
        return (
            (self.config.user, self.config.secret)
            if self.config.user and self.config.secret
            else None
        )

    @cached_property
    def _search_context(self):
        """Returns the opensearch client."""
        return AsyncOpenSearch(
            self.config.hosts,
            scheme=self.schema,
            http_auth=self.http_auth,
            ssl_context=self.ssl_context,
            verify_certs=True,  # default is True, but we want to be explicit
            timeout=self.config.timeout,
            serializer=MSGPECSerializer(self),
            max_retries=self.config.max_retries,
            pool_maxsize=10,
            # default for connection pooling is 10 see:
            # https://github.com/opensearch-project/opensearch-py/blob/main/guides/connection_classes.md
        )

    def __init__(self, name: str, configuration: "OpensearchOutput.Config"):
        super().__init__(name, configuration)
        self._message_backlog = []
        self._flush_task: asyncio.Task | None = None

    async def _asetup(self):
        await super()._asetup()
        flush_timeout = self.config.flush_timeout

        # TODO: improve flush task handling
        async def flush_task() -> None:
            try:
                while True:
                    await asyncio.sleep(flush_timeout)
                    await self.flush()
            except asyncio.CancelledError:
                pass

        self._flush_task = asyncio.create_task(flush_task())

    def describe(self) -> str:
        """Get name of Opensearch endpoint with the host.

        Returns
        -------
        opensearch_output : OpensearchOutput
            Acts as output connector for Opensearch.

        """
        base_description = Output.describe(self)
        return f"{base_description} - Opensearch Output: {self.config.hosts}"

    # @Output._handle_errors
    async def store(self, event: Event) -> None:
        """Store a document in the index defined in the document or to the default index."""
        await self.store_custom(event, event.data.get("_index", self.config.default_index))

    # @Output._handle_errors
    async def store_custom(self, event: Event, target: str) -> None:
        """Store document into backlog to be written into Opensearch with the target index.
        The target index is determined per document by parameter :code:`target`.

        Parameters
        ----------
        document : dict
            Document to be stored into the target index.
        target : str
            Index to store the document in.
        """
        event.state.current_state = EventStateType.STORING_IN_OUTPUT
        document = event.data
        document["_index"] = target
        document["_op_type"] = document.get("_op_type", self.config.default_op_type)
        self.metrics.number_of_processed_events += 1
        self._message_backlog.append(event)
        await self._write_to_search_context()

    async def _write_to_search_context(self):
        """Writes documents from a buffer into Opensearch indices.

        Writes documents in a bulk if the document buffer limit has been reached.
        This reduces connections to Opensearch and improves performance.
        """
        if len(self._message_backlog) >= self.config.message_backlog_size:
            await self.flush()

    # @Metric.measure_time()
    async def flush(self):
        if not self._message_backlog:
            return
        logger.debug("Flushing %d documents to Opensearch", len(self._message_backlog))
        await self._bulk(self._search_context, self._message_backlog)
        self._message_backlog.clear()

    def _chunk_events_by_size(
        self,
        events: list["Event"],
        *,
        chunk_size: int,
        max_chunk_bytes: int,
    ) -> typing.Iterable[list["Event"]]:
        """
        Chunk events into batches respecting chunk_size and (best-effort) max_chunk_bytes.

        Note: max_chunk_bytes is approximate because we estimate bytes via json.dumps.
        """
        batch: list["Event"] = []
        approx_bytes = 0

        for ev in events:
            # best-effort byte estimation
            try:
                approx_bytes += len(json.dumps(ev.data, ensure_ascii=False).encode("utf-8")) + 200
            except Exception:
                approx_bytes += 1000  # fallback guess

            batch.append(ev)

            if len(batch) >= chunk_size or approx_bytes >= max_chunk_bytes:
                yield batch
                batch = []
                approx_bytes = 0

        if batch:
            yield batch

    def _build_bulk_body(self, events: list["Event"], *, default_op_type: str) -> list[dict]:
        """
        Build bulk request body as a list of dicts (action/meta + source lines).
        opensearch-py will serialize this into NDJSON.
        """
        body: list[dict] = []

        for ev in events:
            doc = ev.data
            op_type = doc.get("_op_type", default_op_type)
            index = doc.get("_index")

            if not index:
                # safety: fall back to whatever your pipeline expects
                # (ideally _index is always set before bulk)
                index = doc.get("_index")

            if op_type not in ("index", "create"):
                # keep it strict: your Config only allows create/index
                op_type = default_op_type

            # bulk action line
            action_meta = {op_type: {"_index": index}}
            # optionally pass _id if present
            if "_id" in doc:
                action_meta[op_type]["_id"] = doc["_id"]

            body.append(action_meta)

            # source line: must NOT include bulk meta keys
            source = {k: v for k, v in doc.items() if k not in ("_index", "_op_type")}
            body.append(source)

        return body

    async def _bulk(self, client: AsyncOpenSearch, events: list["Event"]) -> None:
        """
        Async bulk indexing.
        Uses AsyncOpenSearch.bulk directly, and processes per-item results.

        Behavior is intentionally close to your sync version:
        - marks event.state success/failure
        - appends BulkError for failures
        """
        default_op_type = self.config.default_op_type

        for batch in self._chunk_events_by_size(
            events,
            chunk_size=self.config.chunk_size,
            max_chunk_bytes=self.config.max_chunk_bytes,
        ):
            body = self._build_bulk_body(batch, default_op_type=default_op_type)

            try:
                resp = await client.bulk(body=body)
            except OpenSearchException as e:
                # whole bulk request failed → mark all events failed
                for ev in batch:
                    ev.state.current_state = EventStateType.FAILED
                    ev.errors.append(BulkError("Bulk request failed", exception=str(e)))
                continue

            items = resp.get("items", [])
            # One item per document (not per line). Our batch has N events, body has 2N lines.
            # items length should match len(batch) if we're only doing index/create.
            for i, item in enumerate(items):
                if i >= len(batch):
                    break

                ev = batch[i]
                # item shape: {"index": {...}} or {"create": {...}}
                op_type = next(iter(item.keys()), default_op_type)
                info = item.get(op_type, {}) if isinstance(item.get(op_type), dict) else {}

                status = info.get("status")
                error_obj = info.get("error")

                ok = isinstance(status, int) and 200 <= status < 300 and not error_obj
                if ok:
                    ev.state.current_state = EventStateType.STORED_IN_OUTPUT
                    continue

                # normalize error into your BulkError shape
                # error_obj can be dict; keep it as "error" payload if present
                if isinstance(error_obj, dict):
                    message = error_obj.get("reason") or str(error_obj)
                else:
                    message = str(error_obj) if error_obj else "Failed to index document"

                ev.state.current_state = EventStateType.FAILED
                ev.errors.append(
                    BulkError(
                        message,
                        status=str(status) if status is not None else None,
                        exception=None,
                        error=error_obj,  # keep original payload for debugging
                    )
                )

    async def health(self) -> bool:  # type: ignore  # TODO: fix mypy issue
        """Check the health of the component."""
        try:
            resp = await self._search_context.cluster.health(
                params={"timeout": self.config.health_timeout}
            )
        except (OpenSearchException, ConnectionError) as error:
            logger.error("Health check failed: %s", error)
            self.metrics.number_of_errors += 1
            return False
        return super().health() and resp.get("status") in self.config.desired_cluster_status
