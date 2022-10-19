"""
OpensearchOutput
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
        cert: /path/to/cert.crt
"""

import logging
import sys

import opensearchpy as opensearch

from logprep.abc.output import FatalOutputError, Output
from logprep.connector.elasticsearch.output import ElasticsearchOutput

if sys.version_info.minor < 8:  # pragma: no cover
    from backports.cached_property import cached_property  # pylint: disable=import-error
else:
    from functools import cached_property

logging.getLogger("opensearch").setLevel(logging.WARNING)


class OpensearchOutput(ElasticsearchOutput):
    """An OpenSearch output connector."""

    @cached_property
    def _search_context(self):
        return opensearch.OpenSearch(
            self._config.hosts,
            scheme=self.schema,
            http_auth=self.http_auth,
            ssl_context=self.ssl_context,
            timeout=self._config.timeout,
        )

    def describe(self) -> str:
        """Get name of Elasticsearch endpoint with the host.

        Returns
        -------
        opensearch_output : OpensearchOutput
            Acts as output connector for Elasticsearch.

        """
        base_description = Output.describe(self)
        return f"{base_description} - Opensearch Output: {self._config.hosts}"

    def _write_to_search_context(self, document):
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
                    self._search_context,
                    self._message_backlog,
                    max_retries=self._config.max_retries,
                    chunk_size=self._config.message_backlog_size,
                )
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
            _, error_info = bulk_error.popitem()
            data = error_info.get("data") if "data" in error_info else None
            error_type = error_info.get("error").get("type")
            error_reason = error_info.get("error").get("reason")
            reason = f"{error_type}: {error_reason}"
            error_document = self._build_failed_index_document(data, reason)
            self._add_dates(error_document)
            error_documents.append(error_document)

        opensearch.helpers.bulk(self._search_context, error_documents)

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
