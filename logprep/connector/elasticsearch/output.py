"""
ElasticsearchOutput
===================

This section contains the connection settings for Elasticsearch, the default
index, the error index and a buffer size. Documents are sent in batches to Elasticsearch to reduce
the amount of times connections are created.

The documents desired index is the field :code:`_index` in the document. It is deleted afterwards.
If you want to send documents to datastreams, you have to set the field :code:`_op_type: create` in
the document.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    output:
      myelasticsearch_output:
        type: elasticsearch_output
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

import json
import re
import ssl
from functools import cached_property
from logging import Logger
from typing import List, Optional, Pattern, Tuple, Union

import elasticsearch as search
from attr import define, field
from attrs import validators
from elasticsearch import ElasticsearchException, helpers
from opensearchpy import OpenSearchException
from urllib3.exceptions import TimeoutError  # pylint: disable=redefined-builtin

from logprep.abc.output import FatalOutputError, Output
from logprep.metrics.metrics import Metric
from logprep.util.helper import get_dict_size_in_byte
from logprep.util.time import TimeParser


class ElasticsearchOutput(Output):
    """An Elasticsearch output connector."""

    @define(kw_only=True, slots=False)
    class Config(Output.Config):
        """Elastic/Opensearch Output Config"""

        hosts: List[str] = field(
            validator=validators.deep_iterable(
                member_validator=validators.instance_of((str, type(None))),
                iterable_validator=validators.instance_of(list),
            ),
            default=[],
        )
        """Addresses of elasticsearch/opensearch servers. Can be a list of hosts or one single host
        in the format HOST:PORT without specifying a schema. The schema is set automatically to
        https if a certificate is being used."""
        default_index: str = field(validator=validators.instance_of(str))
        """Default index to write to if no index was set in the document or the document could not
        be indexed. The document will be transformed into a string to prevent rejections by the
        default index."""
        error_index: str = field(validator=validators.instance_of(str))
        """Index to write documents to that could not be processed."""
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
        Increases backoff time by 2 seconds per try, but never exceeds 600 seconds."""
        user: Optional[str] = field(validator=validators.instance_of(str), default="")
        """(Optional) User used for authentication."""
        secret: Optional[str] = field(validator=validators.instance_of(str), default="")
        """(Optional) Secret used for authentication."""
        ca_cert: Optional[str] = field(validator=validators.instance_of(str), default="")
        """(Optional) Path to a SSL ca certificate to verify the ssl context."""
        flush_timeout: Optional[int] = field(validator=validators.instance_of(int), default=60)
        """(Optional) Timout after :code:`message_backlog` is flushed if 
        :code:`message_backlog_size` is not reached."""

    __slots__ = ["_message_backlog", "_size_error_pattern"]

    _message_backlog: List

    _size_error_pattern: Pattern[str]

    def __init__(self, name: str, configuration: "ElasticsearchOutput.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self._message_backlog = []
        self._size_error_pattern = re.compile(
            r".*coordinating_operation_bytes=(?P<size>\d+), "
            r"max_coordinating_and_primary_bytes=(?P<max_size>\d+).*"
        )

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
        """Returns the shema. `https` if ssl config is set, else `http`

        Returns
        -------
        str
            the shema
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
    def _search_context(self) -> search.Elasticsearch:
        """Returns a elasticsearch context

        Returns
        -------
        elasticsearch.Elasticsearch
            the eleasticsearch context
        """
        return search.Elasticsearch(
            self._config.hosts,
            scheme=self.schema,
            http_auth=self.http_auth,
            ssl_context=self.ssl_context,
            timeout=self._config.timeout,
        )

    @cached_property
    def _replace_pattern(self):
        return re.compile(r"%{\S+?}")

    def describe(self) -> str:
        """Get name of Elasticsearch endpoint with the host.

        Returns
        -------
        elasticsearch_output : ElasticsearchOutput
            Acts as output connector for Elasticsearch.

        """
        base_description = super().describe()
        return f"{base_description} - ElasticSearch Output: {self._config.hosts}"

    def setup(self):
        super().setup()
        flush_timeout = self._config.flush_timeout
        self._schedule_task(task=self._write_backlog, seconds=flush_timeout)
        try:
            self._search_context.info()
        except (ElasticsearchException, OpenSearchException, TimeoutError) as error:
            raise FatalOutputError(self, error) from error

    def store(self, document: dict):
        """Store a document in the index.

        Parameters
        ----------
        document : dict
           Document to store.

        Returns
        -------
        Returns True to inform the pipeline to call the batch_finished_callback method in the
        configured input
        """
        if document.get("_index") is None:
            document = self._build_failed_index_document(document, "Missing index in document")

        self._add_dates(document)
        self.metrics.number_of_processed_events += 1
        self._message_backlog.append(document)
        self._write_to_search_context()

    def store_custom(self, document: dict, target: str):
        """Store document into backlog to be written into Elasticsearch with the target index.

        Only add to backlog instead of writing the batch and calling batch_finished_callback,
        since store_custom can be called before the event has been fully processed.
        Setting the offset or comiting before fully processing an event can lead to data loss if
        Logprep terminates.

        Parameters
        ----------
        document : dict
            Document to be stored into the target index.
        target : str
            Index to store the document in.
        Raises
        ------
        CriticalOutputError
            Raises if any error except a BufferError occurs while writing into elasticsearch.

        """
        document["_index"] = target
        self._add_dates(document)
        self.metrics.number_of_processed_events += 1
        self._message_backlog.append(document)

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        """Write errors into error topic for documents that failed processing.

        Parameters
        ----------
        error_message : str
           Error message to write into Kafka document.
        document_received : dict
            Document as it was before processing.
        document_processed : dict
            Document after processing until an error occurred.

        """
        self.metrics.number_of_failed_events += 1
        error_document = {
            "error": error_message,
            "original": document_received,
            "processed": document_processed,
            "@timestamp": TimeParser.now().isoformat(),
            "_index": self._config.error_index,
        }
        self._add_dates(error_document)
        self._message_backlog.append(error_document)
        self._write_to_search_context()

    def _build_failed_index_document(self, message_document: dict, reason: str):
        document = {
            "reason": reason,
            "@timestamp": TimeParser.now().isoformat(),
            "_index": self._config.default_index,
        }
        try:
            document["message"] = json.dumps(message_document)
        except TypeError:
            document["message"] = str(message_document)
        return document

    def _add_dates(self, document):
        date_format_matches = self._replace_pattern.findall(document["_index"])
        if date_format_matches:
            now = TimeParser.now()
            for date_format_match in date_format_matches:
                formatted_date = now.strftime(date_format_match[2:-1])
                document["_index"] = re.sub(date_format_match, formatted_date, document["_index"])

    def _write_to_search_context(self):
        """Writes documents from a buffer into Elasticsearch indices.

        Writes documents in a bulk if the document buffer limit has been reached.
        This reduces connections to Elasticsearch.
        The target index is determined per document by the value of the meta field '_index'.
        A configured default index is used if '_index' hasn't been set.

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
        if self.input_connector and hasattr(self.input_connector, "batch_finished_callback"):
            self.input_connector.batch_finished_callback()
        self._message_backlog.clear()

    def _bulk(self, client, actions, *args, **kwargs):
        try:
            helpers.bulk(client, actions, *args, **kwargs)
        except search.SerializationError as error:
            self._handle_serialization_error(error)
        except search.ConnectionError as error:
            self._handle_connection_error(error)
        except helpers.BulkIndexError as error:
            self._handle_bulk_index_error(error)
        except search.exceptions.TransportError as error:
            self._handle_transport_error(error)

    def _handle_serialization_error(self, error: search.SerializationError):
        """Handle serialization error for elasticsearch bulk indexing.

        If at least one document in a chunk can't be serialized, no events will be sent.
        The chunk size is thus set to be the same size as the message backlog size.
        Therefore, it won't result in duplicates once the data is resent.

        Parameters
        ----------
        error : SerializationError
            SerializationError for the error message.

        Raises
        ------
        FatalOutputError
            This causes a pipeline rebuild and gives an appropriate error log message.

        """
        raise FatalOutputError(self, f"{error.args[1]} in document {error.args[0]}")

    def _handle_connection_error(self, error: search.ConnectionError):
        """Handle connection error for elasticsearch bulk indexing.

        No documents will be sent if there is no connection to begin with.
        Therefore, it won't result in duplicates once the the data is resent.
        If the connection is lost during indexing, duplicate documents could be sent.

        Parameters
        ----------
        error : ConnectionError
           ConnectionError for the error message.

        Raises
        ------
        FatalOutputError
            This causes a pipeline rebuild and gives an appropriate error log message.

        """
        raise FatalOutputError(self, error.error)

    def _handle_bulk_index_error(self, error: helpers.BulkIndexError):
        """Handle bulk indexing error for elasticsearch bulk indexing.

        Documents that could not be sent to elastiscsearch due to index errors are collected and
        sent into an error index that should always accept all documents.
        This can lead to a rebuild of the pipeline if this causes another exception.

        Parameters
        ----------
        error : BulkIndexError
           BulkIndexError to collect IndexErrors from.

        """
        error_documents = []
        for bulk_error in error.errors:
            _, error_info = bulk_error.popitem()
            data = error_info.get("data") if "data" in error_info else None
            error_type = error_info.get("error").get("type")
            error_reason = error_info.get("error").get("reason")
            reason = f"{error_type}: {error_reason}"
            error_document = self._build_failed_index_document(data, reason)
            self._add_dates(error_document)
            error_documents.append(error_document)
        self._bulk(self._search_context, error_documents)

    def _handle_transport_error(self, error: search.exceptions.TransportError):
        """Handle transport error for elasticsearch bulk indexing.

        Discard messages that exceed the maximum size if they caused an error.

        Parameters
        ----------
        error : TransportError
           TransportError for the error message.

        """
        if self._config.maximum_message_size_mb is None:
            raise error

        if self._message_exceeds_max_size_error(error):
            (
                messages_under_size_limit,
                messages_over_size_limit,
            ) = self._split_message_backlog_by_size_limit()

            if len(messages_over_size_limit) == 0:
                raise error

            error_documents = self._build_messages_for_large_error_documents(
                messages_over_size_limit
            )
            self._message_backlog = error_documents + messages_under_size_limit
            self._bulk(self._search_context, self._message_backlog)
        else:
            raise error

    def _message_exceeds_max_size_error(self, error):
        if error.status_code == 429:
            if error.error == "circuit_breaking_exception":
                return True

            if error.error == "rejected_execution_exception":
                reason = error.info.get("error", {}).get("reason", {})
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

    def _build_messages_for_large_error_documents(
        self, messages_over_size_limit: List[Tuple[dict, int]]
    ) -> List[dict]:
        """Build error message for messages that were larger than the allowed size limit.

        Only a snipped of the message is stored in the error document, since the original message
        was too large to be written in the first place.

        Parameters
        ----------
        messages_over_size_limit : List[Tuple[dict, int]]
           Messages that were too large with their corresponding sizes in byte.

        """
        error_documents = []
        for message, size in messages_over_size_limit:
            error_message = (
                f"Discarded message that is larger than the allowed size limit "
                f"({size / 10 ** 6} MB/{self._config.maximum_message_size_mb} MB)"
            )
            self._logger.warning(error_message)

            error_document = {
                "processed_snipped": f'{self._encoder.encode(message).decode("utf-8")[:1000]} ...',
                "error": error_message,
                "@timestamp": TimeParser.now().isoformat(),
                "_index": self._config.error_index,
            }
            self._add_dates(error_document)
            error_documents.append(error_document)
        return error_documents
