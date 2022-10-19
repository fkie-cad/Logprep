"""
ElasticsearchOutput
-------------------

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
        cert: /path/to/cert.crt
"""

import json
import re
import ssl
import sys
from logging import Logger
from typing import List, Optional

import arrow
import elasticsearch
from attr import define, field
from attrs import validators
from elasticsearch import helpers

from logprep.abc.output import FatalOutputError, Output

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property


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
        """Amount of documents to store before sending them to Elasticsearch."""
        timeout: int = field(validator=validators.instance_of(int), default=500)
        """Timeout for Elasticsearch connection (default is 500ms)"""
        max_retries: int = field(validator=validators.instance_of(int), default=0)
        """Maximum number of retries for documents rejected with code 429 (default is 0).
        Increases backoff time by 2 seconds per try, but never exceeds 600 seconds."""
        user: Optional[str] = field(validator=validators.instance_of(str), default="")
        """The user used for authentication (optional)."""
        secret: Optional[str] = field(validator=validators.instance_of(str), default="")
        """The secret used for authentication (optional)."""
        ca_cert: Optional[str] = field(validator=validators.instance_of(str), default="")
        """The path to a SSL ca certificate to verify the ssl context (optional)"""

    __slots__ = ["_message_backlog", "_processed_cnt", "_index_cache"]

    _message_backlog: List

    _processed_cnt: int

    _index_cache: dict

    def __init__(self, name: str, configuration: "ElasticsearchOutput.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self._message_backlog = [
            {"_index": self._config.default_index}
        ] * self._config.message_backlog_size
        self._processed_cnt = 0
        self._index_cache = {}

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
    def _search_context(self) -> elasticsearch.Elasticsearch:
        """Returns a elasticsearch context

        Returns
        -------
        elasticsearch.Elasticsearch
            the eleasticsearch context
        """
        return elasticsearch.Elasticsearch(
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

    def _write_to_search_context(self, document):
        """Writes documents from a buffer into Elasticsearch indices.

        Writes documents in a bulk if the document buffer limit has been reached.
        This reduces connections to Elasticsearch.
        The target index is determined per document by the value of the meta field '_index'.
        A configured default index is used if '_index' hasn't been set.

        Parameters
        ----------
        document : dict
           Document to store.

        Returns
        -------
        Returns True to inform the pipeline to call the batch_finished_callback method in the
        configured input
        """
        self._message_backlog[self._processed_cnt] = document
        currently_processed_cnt = self._processed_cnt + 1
        if currently_processed_cnt == self._config.message_backlog_size:
            try:
                helpers.bulk(
                    self._search_context,
                    self._message_backlog,
                    max_retries=self._config.max_retries,
                    chunk_size=self._config.message_backlog_size,
                )
            except elasticsearch.SerializationError as error:
                self._handle_serialization_error(error)
            except elasticsearch.ConnectionError as error:
                self._handle_connection_error(error)
            except helpers.BulkIndexError as error:
                self._handle_bulk_index_error(error)
            self._processed_cnt = 0
            if self.input_connector:
                self.input_connector.batch_finished_callback()
        else:
            self._processed_cnt = currently_processed_cnt

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
        helpers.bulk(self._search_context, error_documents)

    def _handle_connection_error(self, error: elasticsearch.ConnectionError):
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
        raise FatalOutputError(error.error)

    def _handle_serialization_error(self, error: elasticsearch.SerializationError):
        """Handle serialization error for elasticsearch bulk indexing.

        If at least one document in a chunk can't be serialized, no events will be sent.
        The chunk size is thus set to be the same size as the message backlog size.
        Therefore, it won't result in duplicates once the the data is resent.

        Parameters
        ----------
        error : SerializationError
           SerializationError for the error message.

        Raises
        ------
        FatalOutputError
            This causes a pipeline rebuild and gives an appropriate error log message.

        """
        raise FatalOutputError(f"{error.args[1]} in document {error.args[0]}")

    def store(self, document: dict) -> bool:
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
        self._write_to_search_context(document)

    def _build_failed_index_document(self, message_document: dict, reason: str):
        document = {
            "reason": reason,
            "@timestamp": arrow.now().isoformat(),
            "_index": self._config.default_index,
        }
        try:
            document["message"] = json.dumps(message_document)
        except TypeError:
            document["message"] = str(message_document)
        return document

    def store_custom(self, document: dict, target: str):
        """Write document to Elasticsearch into the target index.

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
        self._write_to_search_context(document)

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
        error_document = {
            "error": error_message,
            "original": document_received,
            "processed": document_processed,
            "@timestamp": arrow.now().isoformat(),
            "_index": self._config.error_index,
        }
        self._add_dates(error_document)
        self._write_to_search_context(error_document)

    def _add_dates(self, document):
        date_format_matches = self._replace_pattern.findall(document["_index"])
        if date_format_matches:
            now = arrow.now()
            for date_format_match in date_format_matches:
                formatted_date = now.format(date_format_match[2:-1])
                document["_index"] = re.sub(date_format_match, formatted_date, document["_index"])
