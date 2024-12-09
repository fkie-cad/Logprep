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

import logging
import ssl
from functools import cached_property
from typing import List, Optional

import opensearchpy as search
from attrs import define, field, validators
from opensearchpy import OpenSearchException, helpers
from opensearchpy.serializer import JSONSerializer

from logprep.abc.output import CriticalOutputError, Output
from logprep.metrics.metrics import Metric

logger = logging.getLogger("OpenSearchOutput")


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
            raise search.exceptions.SerializationError(data, e)

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
            default=4, validator=[validators.instance_of(int), validators.gt(1)]
        )
        """Number of threads to use for bulk requests."""
        queue_size: int = field(
            default=4, validator=[validators.instance_of(int), validators.gt(1)]
        )
        """Number of queue size to use for bulk requests."""
        chunk_size: int = field(
            default=500, validator=[validators.instance_of(int), validators.gt(1)]
        )
        """Chunk size to use for bulk requests."""
        max_chunk_bytes: int = field(
            default=100 * 1024 * 1024, validator=[validators.instance_of(int), validators.gt(1)]
        )
        """Max chunk size to use for bulk requests. The default is 100MB."""
        max_retries: int = field(
            default=3, validator=[validators.instance_of(int), validators.gt(0)]
        )
        """Max retries for all requests. Default is 3."""
        desired_cluster_status: list = field(
            default=["green"], validator=validators.instance_of(list)
        )
        """Desired cluster status for health check as list of strings. Default is ["green"]"""
        default_op_type: str = field(
            default="index",
            validator=[validators.instance_of(str), validators.in_(["create", "index"])],
        )
        """Default op_type for indexing documents. Default is 'index',
        Consider using 'create' for data streams or to prevent overwriting existing documents."""

    __slots__ = ["_message_backlog", "_failed"]

    _failed: List
    """Temporary list of failed messages."""

    _message_backlog: List
    """List of messages to be sent to Opensearch."""

    @cached_property
    def ssl_context(self) -> ssl.SSLContext:
        """Returns the ssl context

        Returns
        -------
        SSLContext
            The ssl context
        """
        return (
            ssl.create_default_context(cafile=self._config.ca_cert)
            if self._config.ca_cert
            else None
        )

    @property
    def schema(self) -> str:
        """Returns the schema. `https` if ssl config is set, else `http`

        Returns
        -------
        str
            the schema
        """
        return "https" if self._config.ca_cert else "http"

    @property
    def http_auth(self) -> tuple:
        """Returns the credentials

        Returns
        -------
        tuple
            the credentials in format (user, secret)
        """
        return (
            (self._config.user, self._config.secret)
            if self._config.user and self._config.secret
            else None
        )

    @cached_property
    def _search_context(self):
        """Returns the opensearch client."""
        return search.OpenSearch(
            self._config.hosts,
            scheme=self.schema,
            http_auth=self.http_auth,
            ssl_context=self.ssl_context,
            verify_certs=True,  # default is True, but we want to be explicit
            timeout=self._config.timeout,
            serializer=MSGPECSerializer(self),
            max_retries=self._config.max_retries,
            pool_maxsize=10,
            # default for connection pooling is 10 see:
            # https://github.com/opensearch-project/opensearch-py/blob/main/guides/connection_classes.md
        )

    def __init__(self, name: str, configuration: "OpensearchOutput.Config"):
        super().__init__(name, configuration)
        self._message_backlog = []
        self._failed = []

    def setup(self):
        super().setup()
        flush_timeout = self._config.flush_timeout
        self._schedule_task(task=self._write_backlog, seconds=flush_timeout)

    def describe(self) -> str:
        """Get name of Opensearch endpoint with the host.

        Returns
        -------
        opensearch_output : OpensearchOutput
            Acts as output connector for Opensearch.

        """
        base_description = Output.describe(self)
        return f"{base_description} - Opensearch Output: {self._config.hosts}"

    def store(self, document: dict) -> None:
        """Store a document in the index defined in the document or to the default index.

        Parameters
        ----------
        document : dict
           Document to store.
        """
        self.store_custom(document, document.get("_index", self._config.default_index))

    def store_custom(self, document: dict, target: str) -> None:
        """Store document into backlog to be written into Opensearch with the target index.
        The target index is determined per document by parameter :code:`target`.

        Parameters
        ----------
        document : dict
            Document to be stored into the target index.
        target : str
            Index to store the document in.
        """
        document["_index"] = target
        document["_op_type"] = document.get("_op_type", self._config.default_op_type)
        self.metrics.number_of_processed_events += 1
        self._message_backlog.append(document)
        self._write_to_search_context()

    def _write_to_search_context(self):
        """Writes documents from a buffer into Opensearch indices.

        Writes documents in a bulk if the document buffer limit has been reached.
        This reduces connections to Opensearch and improves performance.
        """
        if len(self._message_backlog) >= self._config.message_backlog_size:
            self._write_backlog()

    @Metric.measure_time()
    def _write_backlog(self):
        if not self._message_backlog:
            return
        logger.debug("Flushing %d documents to Opensearch", len(self._message_backlog))
        try:
            self._bulk(self._search_context, self._message_backlog)
        except CriticalOutputError as error:
            raise error from error
        except Exception as error:  # pylint: disable=broad-except
            logger.error("Failed to index documents: %s", error)
            raise CriticalOutputError(self, str(error), self._message_backlog) from error
        finally:
            self._message_backlog.clear()
            self._failed.clear()

    def _bulk(self, client, actions):
        """Bulk index documents into Opensearch.
        Uses the parallel_bulk function from the opensearchpy library.
        """
        kwargs = {
            "max_chunk_bytes": self._config.max_chunk_bytes,
            "chunk_size": self._config.chunk_size,
            "queue_size": self._config.queue_size,
            "raise_on_error": False,
            "raise_on_exception": False,
        }
        failed = self._failed
        for index, result in enumerate(helpers.parallel_bulk(client, actions, **kwargs)):
            success, item = result
            if success:
                continue
            error_result = item.get(self._config.default_op_type)
            error = error_result.get("error", "Failed to index document")
            data = actions[index]
            failed.append({"errors": error, "event": data})
        if failed:
            raise CriticalOutputError(self, "failed to index", failed)

    def health(self) -> bool:
        """Check the health of the component."""
        try:
            resp = self._search_context.cluster.health(
                params={"timeout": self._config.health_timeout}
            )
        except (OpenSearchException, ConnectionError) as error:
            logger.error("Health check failed: %s", error)
            self.metrics.number_of_errors += 1
            return False
        return super().health() and resp.get("status") in self._config.desired_cluster_status

    def shut_down(self):
        self._write_backlog()
        return super().shut_down()
