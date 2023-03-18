"""
OpensearchOutput
================

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
        ca_cert: /path/to/cert.crt
"""

import logging
from functools import cached_property

import opensearchpy as search
from opensearchpy import helpers

from logprep.abc.output import FatalOutputError, Output
from logprep.connector.elasticsearch.output import ElasticsearchOutput

logging.getLogger("opensearch").setLevel(logging.WARNING)


class OpensearchOutput(ElasticsearchOutput):
    """An OpenSearch output connector."""

    @cached_property
    def _search_context(self):
        return search.OpenSearch(
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

    def _write_backlog(self):
        if not self._message_backlog:
            return
        try:
            helpers.bulk(
                self._search_context,
                self._message_backlog,
                max_retries=self._config.max_retries,
                chunk_size=self._config.message_backlog_size,
            )
        except search.SerializationError as error:
            self._handle_serialization_error(error)
        except search.ConnectionError as error:
            self._handle_connection_error(error)
        except helpers.BulkIndexError as error:
            self._handle_bulk_index_error(error)
        if self.input_connector:
            self.input_connector.batch_finished_callback()
        self._message_backlog.clear()

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
