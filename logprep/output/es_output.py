"""This module contains functionality that allows to send events to Elasticsearch."""

import json
import re
from ssl import create_default_context
from typing import Optional

import arrow
from elasticsearch import Elasticsearch, helpers, SerializationError
from elasticsearch.exceptions import ConnectionError
from elasticsearch.helpers import BulkIndexError

from logprep.connector.connector_factory_error import InvalidConfigurationError
from logprep.input.input import Input
from logprep.output.output import Output, FatalOutputError, CriticalOutputError


class ElasticsearchOutputFactory:
    """Create ElasticsearchOutput for logprep and output communication."""

    @staticmethod
    def create_from_configuration(configuration: dict) -> "ElasticsearchOutput":
        """Create a ElasticsearchOutput connector.

        Parameters
        ----------
        configuration : dict
           Parsed configuration YML.

        Returns
        -------
        elasticsearch_output : ElasticsearchOutput
            Acts as output connector for Elasticsearch.

        Raises
        ------
        InvalidConfigurationError
            If Elasticsearch configuration is invalid.

        """
        if not isinstance(configuration, dict):
            raise InvalidConfigurationError("ElasticsearchOutput: Configuration is not a dict!")

        try:
            es_output = ElasticsearchOutput(
                configuration["elasticsearch"]["host"],
                configuration["elasticsearch"]["port"],
                configuration["elasticsearch"]["default_index"],
                configuration["elasticsearch"]["error_index"],
                configuration["elasticsearch"]["message_backlog"],
                configuration["elasticsearch"].get("timeout", 500),
                configuration["elasticsearch"].get("max_retries", 0),
                configuration["elasticsearch"].get("user"),
                configuration["elasticsearch"].get("secret"),
                configuration["elasticsearch"].get("cert"),
            )
        except KeyError as error:
            raise InvalidConfigurationError(
                f"Elasticsearch: Missing configuration parameter " f"{str(error)}!"
            ) from error

        return es_output


class ElasticsearchOutput(Output):
    """An Elasticsearch output connector."""

    def __init__(
        self,
        host: str,
        port: int,
        default_index: str,
        error_index: str,
        message_backlog_size: int,
        timeout: int,
        max_retries: int,
        user: Optional[str],
        secret: Optional[str],
        cert: Optional[str],
    ):
        self._input = None

        self._host = host
        self._port = port
        self._default_index = default_index
        self._error_index = error_index
        self._max_retries = max_retries

        ssl_context = create_default_context(cafile=cert) if cert else None
        scheme = "https" if cert else "http"
        http_auth = (user, secret) if user and secret else None
        self._es = Elasticsearch(
            [{"host": host, "port": port}],
            scheme=scheme,
            http_auth=http_auth,
            ssl_context=ssl_context,
            timeout=timeout,
        )

        self._max_scroll = "2m"

        self._message_backlog_size = message_backlog_size
        self._message_backlog = [{"_index": default_index}] * self._message_backlog_size
        self._processed_cnt = 0

        self._index_cache = {}
        self._replace_pattern = re.compile(r"%{\S+?}")

    def connect_input(self, input_connector: Input):
        """Connect input connector.

        This connector is used for callbacks.

        Parameters
        ----------
        input_connector : Input
           Input connector to connect this output with.
        """
        self._input = input_connector

    def describe_endpoint(self) -> str:
        """Get name of Elasticsearch endpoint with the host.

        Returns
        -------
        elasticsearch_output : ElasticsearchOutput
            Acts as output connector for Elasticsearch.

        """
        return f"Elasticsearch Output: {self._host}:{self._port}"

    def _write_to_es(self, document):
        """Writes documents from a buffer into Elasticsearch indices.

        Writes documents in a bulk if the document buffer limit has been reached.
        This reduces connections to Elasticsearch.
        The target index is determined per document by the value of the meta field '_index'.
        A configured default index is used if '_index' hasn't been set.

        Parameters
        ----------
        document : dict
           Document to store.

        """
        self._message_backlog[self._processed_cnt] = document
        currently_processed_cnt = self._processed_cnt + 1
        if currently_processed_cnt == self._message_backlog_size:
            try:
                helpers.bulk(
                    self._es,
                    self._message_backlog,
                    max_retries=self._max_retries,
                    chunk_size=self._message_backlog_size,
                )
            except SerializationError as error:
                self._handle_serialization_error(error)
            except ConnectionError as error:
                self._handle_connection_error(error)
            except BulkIndexError as error:
                self._handle_bulk_index_error(error)
            self._processed_cnt = 0

            if self._input:
                self._input.batch_finished_callback()
        else:
            self._processed_cnt = currently_processed_cnt

    def _handle_bulk_index_error(self, error: BulkIndexError):
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
        error_types = {}
        for bulk_error in error.errors:
            error_info = bulk_error.get("index", {})
            data = error_info.get("data")
            reason = f'{error_info["error"]["type"]}: {error_info["error"]["reason"]}'
            error_document = self._build_failed_index_document(data, reason)
            self._add_dates(error_document)
            error_documents.append(error_document)
            if error_types.get(error_info["error"]["type"]) is None:
                error_types[error_info["error"]["type"]] = 1
            else:
                error_types[error_info["error"]["type"]] += 1

        helpers.bulk(self._es, error_documents)

    def _handle_connection_error(self, error: ConnectionError):
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

    def _handle_serialization_error(self, error: SerializationError):
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

    def store(self, document: dict):
        """Store a document in the index.

        Parameters
        ----------
        document : dict
           Document to store.

        """
        if document.get("_index") is None:
            document = self._build_failed_index_document(document, "Missing index in document")

        self._add_dates(document)
        self._write_to_es(document)

    def _build_failed_index_document(self, message_document: dict, reason: str):
        document = {
            "reason": reason,
            "@timestamp": arrow.now().isoformat(),
            "_index": self._default_index,
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
        self._write_to_es(document)

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
            "_index": self._error_index,
        }
        self._add_dates(error_document)
        self._write_to_es(error_document)

    def _add_dates(self, document):
        date_format_matches = self._replace_pattern.findall(document["_index"])
        if date_format_matches:
            now = arrow.now()
            for date_format_match in date_format_matches:
                formatted_date = now.format(date_format_match[2:-1])
                document["_index"] = re.sub(date_format_match, formatted_date, document["_index"])

    @staticmethod
    def _format_message(error: BaseException) -> str:
        return f"{type(error).__name__}: {str(error)}" if str(error) else type(error).__name__
