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
import re
import ssl
from functools import cached_property
from typing import List, Optional, Tuple, Union

import opensearchpy as search
from attrs import define, field, validators
from opensearchpy import OpenSearchException, helpers
from opensearchpy.serializer import JSONSerializer

from logprep.abc.output import CriticalOutputError, FatalOutputError, Output
from logprep.metrics.metrics import Metric
from logprep.util.helper import get_dict_size_in_byte

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
        maximum_message_size_mb: Optional[Union[float, int]] = field(
            validator=validators.optional(validators.instance_of((float, int))),
            converter=(lambda x: x * 10**6 if x else None),
            default=None,
        )
        """(Optional) Maximum estimated size of a document in MB before discarding it if it causes
        an error."""
        timeout: int = field(validator=validators.instance_of(int), default=500)
        """(Optional) Timeout for the connection (default is 500ms)."""
        max_retries: int = field(validator=validators.instance_of(int), default=0)
        """(Optional) Maximum number of retries for documents rejected with code 429 (default is 0).
        Increases backoff time by 2 seconds per try, but never exceeds 600 seconds. When using
        parallel_bulk in the opensearch connector then the backoff time starts with 1 second. With
        each consecutive retry 500 to 1000 ms will be added to the delay, chosen randomly """
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
        desired_cluster_status: list = field(
            default=["green"], validator=validators.instance_of(list)
        )
        """Desired cluster status for health check as list of strings. Default is ["green"]"""

    __slots__ = ["_message_backlog"]

    _message_backlog: List

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
        return search.OpenSearch(
            self._config.hosts,
            scheme=self.schema,
            http_auth=self.http_auth,
            ssl_context=self.ssl_context,
            timeout=self._config.timeout,
            serializer=MSGPECSerializer(self),
        )

    @cached_property
    def _replace_pattern(self):
        return re.compile(r"%{\S+?}")

    @cached_property
    def _size_error_pattern(self):
        return re.compile(
            r".*coordinating_operation_bytes=(?P<size>\d+), "
            r"max_coordinating_and_primary_bytes=(?P<max_size>\d+).*"
        )

    def __init__(self, name: str, configuration: "OpensearchOutput.Config"):
        super().__init__(name, configuration)
        self._message_backlog = []

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
        if document.get("_index") is None:
            document["_index"] = self._config.default_index

        self.metrics.number_of_processed_events += 1
        self._message_backlog.append(document)
        self._write_to_search_context()

    def store_custom(self, document: dict, target: str) -> None:
        """Store document into backlog to be written into Opensearch with the target index.

        Parameters
        ----------
        document : dict
            Document to be stored into the target index.
        target : str
            Index to store the document in.
        """
        document["_index"] = target
        self.metrics.number_of_processed_events += 1
        self._message_backlog.append(document)
        self._write_to_search_context()

    def _write_to_search_context(self):
        """Writes documents from a buffer into Opensearch indices.

        Writes documents in a bulk if the document buffer limit has been reached.
        This reduces connections to Opensearch and improves performance.
        The target index is determined per document by the value of the meta field '_index'.
        A configured default index is used if '_index' hasn't been set. All images are indexed
        using the optype 'create' to prevent overwriting existing documents and to ensure
        usage of data streams.

        Returns
        -------
        Returns True to inform the pipeline to call the batch_finished_callback method in the
        configured input
        """
        if len(self._message_backlog) >= self._config.message_backlog_size:
            self._write_backlog()

    @Metric.measure_time()
    def _write_backlog(self):
        if not self._message_backlog:
            return
        self._bulk(
            self._search_context,
            self._message_backlog,
            max_retries=self._config.max_retries,
            chunk_size=len(self._message_backlog),
        )
        self._message_backlog.clear()

    def _bulk(self, client, actions, *args, **kwargs) -> Optional[List[dict]]:
        failed = []
        succeeded = []
        for index, data in enumerate(
            helpers.parallel_bulk(
                client,
                actions=actions,
                chunk_size=self._config.chunk_size,
                queue_size=self._config.queue_size,
                raise_on_error=False,
                raise_on_exception=False,
            )
        ):
            success, item = data
            if success:
                succeeded.append(item)
            else:
                failed.append({"errors": item, "event": actions[index]})
        if succeeded and logger.isEnabledFor(logging.DEBUG):
            for item in succeeded:
                logger.debug("Document indexed: %s", item)
        if failed:
            raise CriticalOutputError(self, "failed to index", failed)

    def _handle_transport_error(self, error: search.exceptions.TransportError):
        """Handle transport error for opensearch bulk indexing.

        Discard messages that exceed the maximum size if they caused an error.

        Parameters
        ----------
        error : TransportError
           TransportError for the error message.

        """
        if self._message_exceeds_max_size_error(error):
            (
                messages_under_size_limit,
                messages_over_size_limit,
            ) = self._split_message_backlog_by_size_limit()

            if len(messages_over_size_limit) == 0:
                raise FatalOutputError(self, error.error)

            error_documents = self._build_messages_for_large_error_documents(
                messages_over_size_limit
            )
            self._message_backlog = error_documents + messages_under_size_limit
            self._bulk(self._search_context, self._message_backlog)
        else:
            raise FatalOutputError(self, error.error)

    def _message_exceeds_max_size_error(self, error):
        if error.status_code != 429:
            return False
        if error.error == "circuit_breaking_exception":
            return True

        if error.error == "rejected_execution_exception":
            reason = error.info.get("error", {}).get("reason", "")
            match = self._size_error_pattern.match(reason)
            if match and int(match.group("size")) >= int(match.group("max_size")):
                return True
        return False

    def _split_message_backlog_by_size_limit(self):
        messages_under_size_limit = []
        messages_over_size_limit = []
        total_size = 0
        for message in self._message_backlog:
            message_size = get_dict_size_in_byte(message)
            if message_size < self._config.maximum_message_size_mb:
                messages_under_size_limit.append(message)
                total_size += message_size
            else:
                messages_over_size_limit.append((message, message_size))
        return messages_under_size_limit, messages_over_size_limit

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
