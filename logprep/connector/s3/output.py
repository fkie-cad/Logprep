"""
S3Output
===================

This section contains the connection settings for the AWS s3 output connector.

This connector is non-blocking and may skip sending data if previous data has not finished sending.
It doesn't crash if a connection couldn't be established, but sends a warning.

The target bucket is defined by the :code:`bucket` configuration parameter.
The prefix is defined by the value in the field :code:`prefix_field` in the document.

Except for the base prefix, all prefixes can have an arrow date pattern that will be replaced with
the current date. The pattern needs to be wrapped in  :code:`%{...}`.
For example, :code:`prefix-%{YY:MM:DD}` would be replaced with :code:`prefix-%{23:12:06}` if the
date was 2023-12-06.

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    output:
      my_s3_output:
        type: s3_output
        endpoint_url: http://127.0.0.1:9200
        bucket: s3_bucket_name
        error_prefix: some_prefix
        prefix_field: dotted.field
        default_prefix: some_prefix
        base_prefix:
        message_backlog_size: 100000
        connect_timeout:
        max_retries:
        aws_access_key_id:
        aws_secret_access_key:
        ca_cert: /path/to/cert.crt
        use_ssl:
        call_input_callback:
        region_name:

"""
import json
import re
import threading
from collections import defaultdict
from copy import deepcopy
from functools import cached_property
from logging import Logger
from time import time
from typing import DefaultDict, Optional
from uuid import uuid4

import boto3
import msgspec
from attr import define, field
from attrs import validators
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
)

from logprep.abc.output import Output
from logprep.util.helper import get_dotted_field_value
from logprep.util.time import TimeParser


class S3Output(Output):
    """An s3 output connector."""

    @define(kw_only=True, slots=False)
    class Config(Output.Config):
        """S3 Output Config"""

        endpoint_url: str = field(validator=validators.instance_of(str))
        """Address of s3 endpoint in the format SCHEMA:HOST:PORT."""
        bucket: str = field(validator=validators.instance_of(str))
        """Bucket to write to."""
        error_prefix: str = field(validator=validators.instance_of(str))
        """Prefix for documents that could not be processed."""
        prefix_field: str = field(validator=validators.instance_of(str))
        """Field with value to use as prefix for the document."""
        default_prefix: str = field(validator=validators.instance_of(str))
        """Default prefix if no prefix found in the document."""
        base_prefix: Optional[str] = field(validator=validators.instance_of(str), default="")
        """base_prefix prefix (optional)."""
        message_backlog_size: int = field(validator=validators.instance_of(int), default=500)
        """Backlog size to collect messages before sending a batch (default is 500)"""
        connect_timeout: float = field(validator=validators.instance_of(float), default=0.5)
        """Timeout for the AWS s3 connection (default is 500ms)"""
        max_retries: int = field(validator=validators.instance_of(int), default=0)
        """Maximum retry attempts to connect to AWS s3 (default is 0)"""
        aws_access_key_id: Optional[str] = field(
            validator=validators.optional(validators.instance_of(str)), default=None
        )
        """The accees key ID for authentication (optional)."""
        aws_secret_access_key: Optional[str] = field(
            validator=validators.optional(validators.instance_of(str)), default=None
        )
        """The secret used for authentication (optional)."""
        region_name: Optional[str] = field(
            validator=validators.optional(validators.instance_of(str)), default=None
        )
        """Region name for s3 (optional)."""
        ca_cert: Optional[str] = field(
            validator=validators.optional(validators.instance_of(str)), default=None
        )
        """The path to a SSL ca certificate to verify the ssl context (optional)"""
        use_ssl: Optional[bool] = field(validator=validators.instance_of(bool), default=True)
        """Use SSL or not. Is set to true by default (optional)"""
        call_input_callback: Optional[bool] = field(
            validator=validators.instance_of(bool), default=True
        )
        """The input callback is called after the maximum backlog size has been reached 
        if this is set to True (optional)"""

    __slots__ = ["_message_backlog", "_current_backlog_count", "_index_cache"]

    _message_backlog: DefaultDict

    _current_backlog_count: int

    _writing_thread: Optional[threading.Thread]

    _s3_resource: Optional["boto3.resources.factory.s3.ServiceResource"]

    _encoder: msgspec.json.Encoder = msgspec.json.Encoder()

    _base_prefix: str

    def __init__(self, name: str, configuration: "S3Output.Config", logger: Logger):
        super().__init__(name, configuration, logger)
        self._message_backlog = defaultdict(list)
        self._current_backlog_count = 0
        self._writing_thread = None
        self._base_prefix = f"{self._config.base_prefix}/" if self._config.base_prefix else ""
        self._s3_resource = None
        self._setup_s3_resource()

    def _setup_s3_resource(self):
        session = boto3.Session(
            aws_access_key_id=self._config.aws_access_key_id,
            aws_secret_access_key=self._config.aws_secret_access_key,
            region_name=self._config.region_name,
        )
        config = boto3.session.Config(
            connect_timeout=self._config.connect_timeout, retries={"max_attempts": 0}
        )
        self._s3_resource = session.resource(
            "s3",
            endpoint_url=f"{self._config.endpoint_url}",
            verify=self._config.ca_cert,
            use_ssl=self._config.use_ssl,
            config=config,
        )

    @property
    def s3_resource(self):
        """Return s3 resource"""
        return self._s3_resource

    @cached_property
    def _replace_pattern(self):
        return re.compile(r"%{\S+?}")

    def describe(self) -> str:
        """Get name of s3 endpoint with the host.

        Returns
        -------
        s3_output : S3Output
            Acts as output connector for AWS s3.

        """
        base_description = super().describe()
        return f"{base_description} - S3 Output: {self._config.endpoint_url}"

    def _add_dates(self, prefix):
        date_format_matches = self._replace_pattern.findall(prefix)
        if date_format_matches:
            now = TimeParser.now()
            for date_format_match in date_format_matches:
                formatted_date = now.strftime(date_format_match[2:-1])
                prefix = re.sub(date_format_match, formatted_date, prefix)
        return prefix

    def _write_to_s3_resource(self, document: dict, prefix: str):
        """Writes a document into s3 bucket using given prefix.

        Parameters
        ----------
        document : dict
           Document to store.

        Returns
        -------
        Returns True to inform the pipeline to call the batch_finished_callback method in the
        configured input
        """
        prefix = self._add_dates(prefix)
        prefix = f"{self._base_prefix}{prefix}"
        self._message_backlog[prefix].append(document)

        backlog_count = self._current_backlog_count + 1
        if backlog_count == self._config.message_backlog_size:
            if self._writing_thread is None or not self._writing_thread.is_alive():
                message_backlog = deepcopy(self._message_backlog)
                self._writing_thread = threading.Thread(
                    target=self._write_document_batches, args=(message_backlog,)
                )
                self._writing_thread.start()
                return True
        self._current_backlog_count = backlog_count
        return False

    def _write_document_batches(self, message_backlog):
        self._logger.info(f"Writing {self._current_backlog_count + 1} documents to s3")
        for prefix_mb, document_batch in message_backlog.items():
            self._write_document_batch(document_batch, f"{prefix_mb}/{time()}-{uuid4()}")
        self._message_backlog.clear()
        self._current_backlog_count = 0

    def _write_document_batch(self, document_batch: dict, identifier: str):
        try:
            self._write_to_s3(document_batch, identifier)
        except EndpointConnectionError:
            self._logger.warning(f"{self.describe()}: Could not connect to the endpoint URL")
        except ConnectionClosedError:
            self._logger.warning(
                f"{self.describe()}: "
                f"Connection was closed before we received a valid response from endpoint URL"
            )
        except (BotoCoreError, ClientError) as error:
            self._logger.warning(f"{self.describe()}: {error}")

    def _write_to_s3(self, document_batch: dict, identifier: str):
        self._logger.debug(f'Writing "{identifier}" to s3 bucket "{self._config.bucket}"')
        s3_obj = self.s3_resource.Object(self._config.bucket, identifier)
        s3_obj.put(Body=self._encoder.encode(document_batch), ContentType="application/json")

    def store(self, document: dict):
        """Store a document into s3 bucket.

        Parameters
        ----------
        document : dict
           Document to store.
        """
        self.metrics.number_of_processed_events += 1

        prefix_value = get_dotted_field_value(document, self._config.prefix_field)
        if prefix_value is None:
            document = self._build_no_prefix_document(
                document, f"Prefix field '{self._config.prefix_field}' empty or missing in document"
            )
            prefix_value = self._config.default_prefix

        batch_finished = self._write_to_s3_resource(document, prefix_value)
        if self._config.call_input_callback and batch_finished and self.input_connector:
            self.input_connector.batch_finished_callback()

    @staticmethod
    def _build_no_prefix_document(message_document: dict, reason: str):
        document = {
            "reason": reason,
            "@timestamp": TimeParser.now().isoformat(),
        }
        try:
            document["message"] = json.dumps(message_document)
        except TypeError:
            document["message"] = str(message_document)
        return document

    def store_custom(self, document: dict, target: str):
        """Write document into s3 bucket using the target prefix.

        Parameters
        ----------
        document : dict
            Document to be stored into the target prefix.
        target : str
            Prefix for the document.

        """
        self.metrics.number_of_processed_events += 1
        self._write_to_s3_resource(document, target)

    def store_failed(self, error_message: str, document_received: dict, document_processed: dict):
        """Write errors into s3 bucket using error prefix for documents that failed processing.

        Parameters
        ----------
        error_message : str
           Error message to write into document.
        document_received : dict
            Document as it was before processing.
        document_processed : dict
            Document after processing until an error occurred.

        """
        error_document = {
            "error": error_message,
            "original": document_received,
            "processed": document_processed,
            "@timestamp": TimeParser.now().isoformat(),
        }
        self._write_to_s3_resource(error_document, self._config.error_prefix)
