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

import contextlib
import logging
import ssl
import typing
from collections.abc import Sequence
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
from logprep.ng.abc.event import Event
from logprep.ng.abc.output import Output

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
        """Number of threads to use for bulk requests.
        DEPRECATED: This Argument is deprecated and doesnt do anything anymore,
        it will be removed in the future"""

        queue_size: int = field(
            default=4, validator=(validators.instance_of(int), validators.gt(1))
        )
        """Number of queue size to use for bulk requests.
        DEPRECATED: This Argument is deprecated and doesnt do anything anymore,
        it will be removed in the future"""

        chunk_size: int = field(
            default=500, validator=(validators.instance_of(int), validators.gt(1))
        )
        """Chunk size to use for bulk requests."""

        max_chunk_bytes: int = field(
            default=100 * 1024 * 1024,
            validator=(validators.instance_of(int), validators.gt(1)),
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
            validator=(
                validators.instance_of(str),
                validators.in_(["create", "index"]),
            ),
        )
        """Default op_type for indexing documents. Default is 'index',
        Consider using 'create' for data streams or to prevent overwriting existing documents."""

    __slots__ = ("_search_context",)

    """List of messages to be sent to Opensearch."""

    @property
    def _metrics(self) -> Output.Metrics:
        """Provides the properly typed metrics object"""
        return typing.cast(Output.Metrics, self.metrics)

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

    def describe(self) -> str:
        """Get name of Opensearch endpoint with the host."""
        base_description = Output.describe(self)
        return f"{base_description} - Opensearch Output: {self.config.hosts}"

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
            verify_certs=True,  # default is True, but we want to be explicit
            timeout=self.config.timeout,
            serializer=MSGPECSerializer(self),
            max_retries=self.config.max_retries,
            pool_maxsize=10,
            # default for connection pooling is 10 see:
            # https://github.com/opensearch-project/opensearch-py/blob/main/guides/connection_classes.md
        )
        return await super().setup()

    async def _store_batch(
        self, events: Sequence[Event], target: str | None = None
    ) -> Sequence[Event]:
        logger.debug("Flushing %d documents to opensearch with target '%s'", len(events), target)
        target = target if target else self.config.default_index

        for event in events:
            document = event.data
            document["_index"] = document.get("_index", target)
            document["_op_type"] = document.get("_op_type", self.config.default_op_type)

        await self._bulk(self._search_context, events)
        self._metrics.number_of_processed_events += len(events)
        return events

    async def _bulk(self, client: AsyncOpenSearch, events: Sequence[Event]) -> None:
        """Bulk index documents into Opensearch. Uses the parallel_bulk function from the opensearchpy library.
        The error information is stored in a document with the following structure:
            json
            {
                "op_type": {
                    "error": "error message",
                    "status": "status_code",
                    "exception": "exception message"
                    }
                }
            }
        """

        actions = (event.data for event in events)

        index = 0
        async with contextlib.aclosing(
            helpers.async_streaming_bulk(
                client,
                actions,
                max_chunk_bytes=self.config.max_chunk_bytes,
                chunk_size=self.config.chunk_size,
                raise_on_error=False,
                raise_on_exception=False,
            )
        ) as send_results:
            async for success, item in send_results:
                event = events[index]
                index += 1

                if success:
                    continue

                logger.debug("event failed to send: %s", item)

                op_infos = item.values()
                error_info = op_infos[0] if len(op_infos) > 0 else {}

                error = BulkError(error_info.get("error", "Failed to index document"), **error_info)
                event.errors.append(error)

    async def health(self) -> bool:  # type: ignore[override]
        """Check the health of the component."""
        try:
            resp = await self._search_context.cluster.health(
                params={"timeout": self.config.health_timeout}
            )
        except (OpenSearchException, ConnectionError) as error:
            logger.error("Health check failed: %s", error)
            self._metrics.number_of_errors += 1
            return False
        return await super().health() and resp.get("status") in self.config.desired_cluster_status

    async def shut_down(self):
        self._search_context.close()
        await super().shut_down()
