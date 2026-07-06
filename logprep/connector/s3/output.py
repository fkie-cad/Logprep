"""
S3Output
===================

This section contains the connection settings for the AWS s3 output connector.

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

import logging
import re
import typing
from collections import defaultdict
from functools import cached_property
from time import time
from typing import Any, DefaultDict, Optional
from uuid import uuid4

import boto3
import msgspec
from attrs import define, field, validators
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
)

from logprep.abc.output import FatalOutputError, Output
from logprep.metrics.metrics import CounterMetric, Metric
from logprep.util.helper import get_dotted_field_value
from logprep.util.time import TimeParser


def _handle_s3_error(func):
    def _inner(self: "S3Output", *args) -> Any:
        try:
            return func(self, *args)
        except EndpointConnectionError as error:
            raise FatalOutputError(self, "Could not connect to the endpoint URL") from error
        except ConnectionClosedError as error:
            raise FatalOutputError(
                self,
                "Connection was closed before we received a valid response from endpoint URL",
            ) from error
        except (BotoCoreError, ClientError) as error:
            raise FatalOutputError(self, str(error)) from error

        return None

    return _inner


logger = logging.getLogger("S3Output")


class S3Output(Output):
    """An s3 output connector."""

    @define(kw_only=True, slots=False)
    class Config(Output.Config):
        """
        S3 Output Config

        .. security-best-practice::
           :title: Output Connectors - S3Output

           It is suggested to activate SSL for a secure connection. In order to do that set
           :code:`use_ssl` and the corresponding :code:`ca_cert`.
        """

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
        base_prefix: str = field(validator=validators.instance_of(str), default="")
        """base_prefix prefix (optional)."""
        message_backlog_size: int = field(validator=validators.instance_of(int), default=500)
        """Backlog size to collect messages before sending a batch (default is 500)"""
        connect_timeout: float = field(validator=validators.instance_of(float), default=0.5)
        """Timeout for the AWS s3 connection (default is 500ms)"""
        max_retries: int = field(validator=validators.instance_of(int), default=0)
        """Maximum retry attempts to connect to AWS s3 (default is 0)"""
        aws_access_key_id: str | None = field(
            validator=validators.optional(validators.instance_of(str)), default=None
        )
        """The accees key ID for authentication (optional)."""
        aws_secret_access_key: str | None = field(
            validator=validators.optional(validators.instance_of(str)), default=None
        )
        """The secret used for authentication (optional)."""
        region_name: str | None = field(
            validator=validators.optional(validators.instance_of(str)), default=None
        )
        """Region name for s3 (optional)."""
        ca_cert: str | None = field(
            validator=validators.optional(validators.instance_of(str)), default=None
        )
        """The path to a SSL ca certificate to verify the ssl context (optional)"""
        use_ssl: Optional[bool] = field(validator=validators.instance_of(bool), default=True)
        """Use SSL or not. Is set to true by default (optional)"""
        call_input_callback: bool = field(validator=validators.instance_of(bool), default=True)
        """The input callback is called after the maximum backlog size has been reached
        if this is set to True (optional)"""
        flush_timeout: int = field(validator=validators.instance_of(int), default=60)
        """(Optional) Timeout after :code:`message_backlog` is flushed if
        :code:`message_backlog_size` is not reached."""

    @define(kw_only=True)
    class Metrics(Output.Metrics):
        """Tracks statistics about this output"""

        number_of_successful_writes: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Number of events that were successfully written to s3",
                name="number_of_successful_writes",
            )
        )
        """Number of events that were successfully written to s3"""

    __slots__ = ["_message_backlog", "_base_prefix"]

    _message_backlog: DefaultDict

    _base_prefix: str

    def __init__(self, name: str, configuration: "S3Output.Config"):
        super().__init__(name, configuration)
        self._message_backlog = defaultdict(list)
        self._base_prefix = f"{self.config.base_prefix}/" if self.config.base_prefix else ""

    @property
    def config(self) -> Config:
        """Provides the properly typed configuration object"""
        return typing.cast(S3Output.Config, self._config)

    @cached_property
    def _s3_resource(self) -> boto3.resources.factory.ServiceResource:
        session = boto3.Session(
            aws_access_key_id=self.config.aws_access_key_id,
            aws_secret_access_key=self.config.aws_secret_access_key,
            region_name=self.config.region_name,
        )
        config = boto3.session.Config(
            connect_timeout=self.config.connect_timeout,
            retries={"max_attempts": self.config.max_retries},
        )
        return session.resource(
            "s3",
            endpoint_url=f"{self.config.endpoint_url}",
            verify=self.config.ca_cert,
            use_ssl=self.config.use_ssl,
            config=config,
        )

    @property
    def _backlog_size(self) -> int:
        return sum(map(len, self._message_backlog.values()))

    @cached_property
    def _replace_pattern(self) -> re.Pattern[str]:
        return re.compile(r"%{\S+?}")

    def _describe(self) -> str:
        """Get name of s3 endpoint with the host.

        Returns
        -------
        s3_output : S3Output
            Acts as output connector for AWS s3.

        """
        return f"{super()._describe()} - S3 Output: {self.config.endpoint_url}"

    @_handle_s3_error
    def setup(self) -> None:
        super().setup()
        flush_timeout = self.config.flush_timeout
        self._schedule_task(task=self._write_backlog, seconds=flush_timeout)

        _ = self._s3_resource.meta.client.head_bucket(Bucket=self.config.bucket)

    def store(self, document: dict) -> None:
        """Store a document into s3 bucket.

        Parameters
        ----------
        document : dict
           Document to store.
        """
        self.metrics.number_of_processed_events += 1
        prefix_value = get_dotted_field_value(document, self.config.prefix_field)
        if prefix_value is None:
            document = self._build_no_prefix_document(
                document, f"Prefix field '{self.config.prefix_field}' empty or missing in document"
            )
            prefix_value = self.config.default_prefix
        if not isinstance(prefix_value, str):
            raise ValueError(
                f"encountered non-string value to store (type {type(prefix_value)}): {prefix_value}"
            )
        self._add_to_backlog(document, prefix_value)
        self._write_to_s3_resource()

    def store_custom(self, document: dict, target: str) -> None:
        """Store document into backlog to be written into s3 bucket using the target prefix.

        Only add to backlog instead of writing the batch and calling batch_finished_callback,
        since store_custom can be called before the event has been fully processed.
        Setting the offset or comiting before fully processing an event can lead to data loss if
        Logprep terminates.

        Parameters
        ----------
        document : dict
            Document to be stored into the target prefix.
        target : str
            Prefix for the document.

        """
        self.metrics.number_of_processed_events += 1
        self._add_to_backlog(document, target)

    def _add_dates(self, prefix: str) -> str:
        date_format_matches = self._replace_pattern.findall(prefix)
        if date_format_matches:
            now = TimeParser.now()
            for date_format_match in date_format_matches:
                formatted_date = now.strftime(date_format_match[2:-1])
                prefix = re.sub(date_format_match, formatted_date, prefix)
        return prefix

    @Metric.measure_time()
    def _write_to_s3_resource(self) -> None:
        """Writes a document into s3 bucket using given prefix."""
        if self._backlog_size >= self.config.message_backlog_size:
            self._write_backlog()

    def _add_to_backlog(self, document: dict, prefix: str) -> None:
        """Adds document to backlog and adds a a prefix.

        Parameters
        ----------
        document : dict
           Document to store in backlog.
        """
        prefix = self._add_dates(prefix)
        prefix = f"{self._base_prefix}{prefix}"
        self._message_backlog[prefix].append(document)

    def _write_backlog(self) -> None:
        """Write to s3 if it is not already writing."""
        if not self._message_backlog:
            return

        logger.info("Writing %s documents to s3", self._backlog_size)
        for prefix_mb, document_batch in self._message_backlog.items():
            self._write_document_batch(document_batch, f"{prefix_mb}/{time()}-{uuid4()}")
        self._message_backlog.clear()

        if not self.config.call_input_callback:
            return

    @_handle_s3_error
    def _write_document_batch(self, document_batch: dict, identifier: str) -> None:
        logger.debug('Writing "%s" to s3 bucket "%s"', identifier, self.config.bucket)
        s3_obj = self._s3_resource.Object(self.config.bucket, identifier)
        s3_obj.put(Body=self._encoder.encode(document_batch), ContentType="application/json")
        self.metrics.number_of_successful_writes += len(document_batch)

    def _build_no_prefix_document(self, message_document: dict, reason: str) -> dict:
        document = {
            "reason": reason,
            "@timestamp": TimeParser.now().isoformat(),
        }
        try:
            document["message"] = self._encoder.encode(message_document).decode("utf-8")
        except (msgspec.EncodeError, TypeError):
            document["message"] = str(message_document)
        return document
