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
from attrs import define, field, validators
from opensearchpy import helpers
from opensearchpy.serializer import JSONSerializer

from logprep.abc.output import Output
from logprep.connector.elasticsearch.output import ElasticsearchOutput

logging.getLogger("opensearch").setLevel(logging.WARNING)


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

    def loads(self, data):
        return self._decoder.decode(data)


class OpensearchOutput(ElasticsearchOutput):
    """An OpenSearch output connector."""

    @define(kw_only=True, slots=False)
    class Config(ElasticsearchOutput.Config):
        """Config for OpensearchOutput."""

        parallel_bulk: bool = field(default=True, validator=validators.instance_of(bool))
        """Configure if all events in the backlog should be send, in parallel, via multiple threads
        to Opensearch. (Default: :code:`True`)"""
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

    def describe(self) -> str:
        """Get name of Elasticsearch endpoint with the host.

        Returns
        -------
        opensearch_output : OpensearchOutput
            Acts as output connector for Elasticsearch.

        """
        base_description = Output.describe(self)
        return f"{base_description} - Opensearch Output: {self._config.hosts}"

    def _bulk(self, client, actions, *args, **kwargs):
        try:
            if self._config.parallel_bulk:
                self._parallel_bulk(client, actions, *args, **kwargs)
                return
            helpers.bulk(client, actions, *args, **kwargs)
        except search.SerializationError as error:
            self._handle_serialization_error(error)
        except search.ConnectionError as error:
            self._handle_connection_error(error)
        except helpers.BulkIndexError as error:
            self._handle_bulk_index_error(error)
        except search.exceptions.TransportError as error:
            self._handle_transport_error(error)

    def _parallel_bulk(self, client, actions, *args, **kwargs):
        for success, item in helpers.parallel_bulk(
            client,
            actions=actions,
            chunk_size=self._config.chunk_size,
            queue_size=self._config.queue_size,
            raise_on_error=True,
            raise_on_exception=True,
        ):
            if not success:
                result = item[list(item.keys())[0]]
                if "error" in result:
                    raise result.get("error")
