"""This module contains functionality that allows to send events to OpenSearch."""

import json
import logging
import re
import ssl
import sys
from typing import List, Optional

import arrow
from attrs import define, field, validators
import opensearchpy as opensearch
from logprep.abc.output import FatalOutputError, Output

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property

logging.getLogger("opensearch").setLevel(logging.WARNING)


class OpensearchOutput(Output):
    """An OpenSearch output connector."""

    @define(kw_only=True, slots=False)
    class Config(Output.Config):
        """Confluent Kafka Output Config"""

        hosts: List[str] = field(
            validator=validators.deep_iterable(
                member_validator=validators.instance_of((str, type(None))),
                iterable_validator=validators.instance_of(list),
            ),
            default=[],
        )
        default_index: str = field(validator=validators.instance_of(str))
        error_index: str = field(validator=validators.instance_of(str))
        message_backlog_size: int = field(validator=validators.instance_of(int))
        timeout: int = field(validator=validators.instance_of(int))
        max_scroll: str = field(validator=validators.instance_of(str), default="2m")
        max_retries: int = field(validator=validators.instance_of(int), default=1)
        user: Optional[str] = field(validator=validators.instance_of(str), default="")
        secret: Optional[str] = field(validator=validators.instance_of(str), default="")
        cert: Optional[str] = field(validator=validators.instance_of(str), default="")

    __slots__ = ["_message_backlog", "_processed_cnt", "_index_cache"]

    _message_backlog: List

    _processed_cnt: int

    _index_cache: dict

    def __init__(self, name: str, configuration: "Input.Config", logger: logging.Logger):
        super().__init__(name, configuration, logger)
        self._message_backlog = [
            {"_index": self._config.default_index}
        ] * self._config.message_backlog_size
        self._processed_cnt = 0
        self._index_cache = {}

    @cached_property
    def ssl_context(self):
        return ssl.create_default_context(cafile=self._config.cert) if self._config.cert else None

    @property
    def schema(self):
        return "https" if self._config.cert else "http"

    @property
    def http_auth(self):
        return (
            (self._config.user, self._config.secret)
            if self._config.user and self._config.secret
            else None
        )

    @cached_property
    def _os(self):
        return opensearch.OpenSearch(
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
        return f"{base_description} - Opensearch Output: {self._config.hosts}"

    def _write_to_os(self, document):
        """Writes documents from a buffer into OpenSearch indices.

        Writes documents in a bulk if the document buffer limit has been reached.
        This reduces connections to OpenSearch.
        The target index is determined per document by the value of the meta field '_index'.
        A configured default index is used if '_index' hasn't been set.

        Parameters
        ----------
        document : dict
           Document to store.

        """
        self._message_backlog[self._processed_cnt] = document
        currently_processed_cnt = self._processed_cnt + 1
        if currently_processed_cnt == self._config.message_backlog_size:
            try:
                opensearch.helpers.bulk(
                    self._os,
                    self._message_backlog,
                    max_retries=self._config.max_retries,
                    chunk_size=self._config.message_backlog_size,
                )
                self.metrics.number_of_processed_events += currently_processed_cnt
            except opensearch.SerializationError as error:
                self._handle_serialization_error(error)
            except opensearch.ConnectionError as error:
                self._handle_connection_error(error)
            except opensearch.helpers.BulkIndexError as error:
                self._handle_bulk_index_error(error)
            self._processed_cnt = 0
            if self.input_connector:
                self.input_connector.batch_finished_callback()
        else:
            self._processed_cnt = currently_processed_cnt

    def _handle_bulk_index_error(self, error: opensearch.helpers.BulkIndexError):
        """Handle bulk indexing error for OpenSearch bulk indexing.

        Documents that could not be sent to OpenSearch due to index errors are collected and
        sent into an error index that should always accept all documents.
        This can lead to a rebuild of the pipeline if this causes another exception.

        Parameters
        ----------
        error : BulkIndexError
           BulkIndexError to collect IndexErrors from.

        """
        error_documents = []
        for bulk_error in error.errors:
            error_info = bulk_error.get("index", {})
            data = error_info.get("data")
            reason = f'{error_info["error"]["type"]}: {error_info["error"]["reason"]}'
            error_document = self._build_failed_index_document(data, reason)
            self._add_dates(error_document)
            error_documents.append(error_document)

        opensearch.helpers.bulk(self._os, error_documents)

    def _handle_connection_error(self, error: ConnectionError):
        """Handle connection error for OpenSearch bulk indexing.

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

    def _handle_serialization_error(self, error: opensearch.SerializationError):
        """Handle serialization error for OpenSearch bulk indexing.

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
        self._write_to_os(document)

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
        """Write document to OpenSearch into the target index.

        Parameters
        ----------
        document : dict
            Document to be stored into the target index.
        target : str
            Index to store the document in.
        Raises
        ------
        CriticalOutputError
            Raises if any error except a BufferError occurs while writing into OpenSearch.

        """
        document["_index"] = target
        self._add_dates(document)
        self._write_to_os(document)

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
        self._write_to_os(error_document)

    def _add_dates(self, document):
        date_format_matches = self._replace_pattern.findall(document["_index"])
        if date_format_matches:
            now = arrow.now()
            for date_format_match in date_format_matches:
                formatted_date = now.format(date_format_match[2:-1])
                document["_index"] = re.sub(date_format_match, formatted_date, document["_index"])
