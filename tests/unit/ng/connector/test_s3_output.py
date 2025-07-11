# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
import logging
from copy import deepcopy
from unittest import mock

import pytest
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectionClosedError,
    EndpointConnectionError,
)

from logprep.abc.output import FatalOutputError
from logprep.factory import Factory
from logprep.util.time import TimeParser
from tests.unit.connector.base import BaseOutputTestCase


class NotJsonSerializableMock:
    pass


class TestS3Output(BaseOutputTestCase):
    CONFIG = {
        "type": "s3_output",
        "endpoint_url": "http://localhost:23423",
        "aws_access_key_id": "foo_aws_access_key_id",
        "aws_secret_access_key": "foo_aws_secret_access_key",
        "bucket": "foo_bucket",
        "default_prefix": "foo_default_prefix",
        "prefix_field": "foo_prefix_field",
        "error_prefix": "foo_error_prefix",
        "message_backlog_size": 1,
    }

    expected_metrics = [
        "logprep_processing_time_per_event",
        "logprep_number_of_processed_events",
        "logprep_number_of_warnings",
        "logprep_number_of_errors",
        "logprep_number_of_successful_writes",
    ]

    def test_describe_returns_s3_output(self):
        assert (
            self.object.describe()
            == "S3Output (Test Instance Name) - S3 Output: http://localhost:23423"
        )

    base_prefix_tests_cases = ["", "test"]

    @pytest.mark.parametrize("base_prefix", base_prefix_tests_cases)
    def test_store_sends_with_default_prefix(self, base_prefix):
        event = {"field": "content"}
        default_prefix = (
            f"{base_prefix}/foo_default_prefix" if base_prefix else "foo_default_prefix"
        )
        expected = {
            default_prefix: [
                {
                    "message": '{"field":"content"}',
                    "reason": "Prefix field 'foo_prefix_field' empty or missing in document",
                }
            ]
        }
        s3_config = deepcopy(self.CONFIG)
        s3_config.update({"message_backlog_size": 2, "base_prefix": base_prefix})
        s3_output = Factory.create({"s3": s3_config})

        s3_output.store(event)

        assert default_prefix in s3_output._message_backlog
        assert len(s3_output._message_backlog[default_prefix]) == 1
        assert "@timestamp" in s3_output._message_backlog[default_prefix][0]
        assert s3_output._message_backlog[default_prefix][0].pop("@timestamp")
        assert s3_output._message_backlog == expected

    @pytest.mark.parametrize("base_prefix", base_prefix_tests_cases)
    def test_store_sends_event_to_with_expected_prefix_if_prefix_missing_in_event(
        self, base_prefix
    ):
        event = {"field": "content"}
        default_prefix = f"{base_prefix}/default_prefix" if base_prefix else "default_prefix"
        expected = {
            "message": '{"field":"content"}',
            "reason": "Prefix field 'foo_prefix_field' empty or missing in document",
        }
        s3_config = deepcopy(self.CONFIG)
        s3_config.update({"default_prefix": default_prefix, "message_backlog_size": 2})
        s3_output = Factory.create({"s3": s3_config})

        s3_output.store(event)

        assert s3_output._message_backlog[default_prefix][0].pop("@timestamp")
        assert s3_output._message_backlog[default_prefix][0] == expected

    @pytest.mark.parametrize("base_prefix", base_prefix_tests_cases)
    def test_store_custom_writes_event_with_expected_prefix(self, base_prefix):
        custom_prefix = f"{base_prefix}/custom_prefix" if base_prefix else "custom_prefix"
        event = {"field": "content"}
        expected = {"field": "content"}

        s3_config = deepcopy(self.CONFIG)
        s3_config.update({"message_backlog_size": 2})
        s3_output = Factory.create({"s3": s3_config})

        s3_output.store_custom(event, custom_prefix)
        assert s3_output._message_backlog[custom_prefix][0] == expected

    def test_create_s3_building_prefix_with_invalid_json(self):
        expected = {"reason": "A reason for failed prefix"}
        failed_document = self.object._build_no_prefix_document(
            {"invalid_json": NotJsonSerializableMock(), "something_valid": "im_valid!"},
            "A reason for failed prefix",
        )
        assert "NotJsonSerializableMock" in failed_document.pop("message")
        assert failed_document.pop("@timestamp")
        assert failed_document == expected

    @pytest.mark.parametrize(
        "error, message",
        [
            (
                EndpointConnectionError(endpoint_url="foo"),
                r".*Could not connect to the endpoint URL.*",
            ),
            (
                ConnectionClosedError(endpoint_url="foo"),
                r".*Connection was closed before we received a valid response from endpoint URL.*",
            ),
            (
                ClientError(error_response={"foo": "bar"}, operation_name="foo"),
                r".*An error occurred \(\w+\) when calling the foo operation: \w+.*",
            ),
            (
                BotoCoreError(),
                r".*An unspecified error occurred.*",
            ),
        ],
    )
    def test_write_document_batch_calls_handles_errors(self, caplog, error, message):
        with caplog.at_level(logging.WARNING):
            with mock.patch.object(
                self.object._s3_resource,
                "Object",
                side_effect=error,
            ):
                with pytest.raises(FatalOutputError, match=message):
                    self.object._write_document_batch({"dummy": "event"}, "dummy_identifier")

    def test_write_to_s3_resource_sets_current_backlog_count_and_below_max_backlog(self):
        s3_config = deepcopy(self.CONFIG)
        message_backlog_size = 5
        s3_config.update({"message_backlog_size": message_backlog_size})
        s3_output = Factory.create({"s3": s3_config})
        assert self._calculate_backlog_size(s3_output) == 0
        for idx in range(1, message_backlog_size):
            s3_output._add_to_backlog({"dummy": "event"}, "write_to_s3")
            s3_output._write_to_s3_resource()
            assert self._calculate_backlog_size(s3_output) == idx

    def test_write_to_s3_resource_sets_current_backlog_count_and_is_max_backlog(self):
        s3_config = deepcopy(self.CONFIG)
        message_backlog_size = 5
        s3_config.update({"message_backlog_size": message_backlog_size})
        s3_output = Factory.create({"s3": s3_config})

        s3_output._write_document_batch = mock.MagicMock()
        s3_output._write_document_batch.assert_not_called()

        # Backlog not full
        for idx in range(message_backlog_size - 1):
            s3_output._add_to_backlog({"dummy": "event"}, "write_to_s3")
            s3_output._write_to_s3_resource()
            assert self._calculate_backlog_size(s3_output) == idx + 1
        s3_output._write_document_batch.assert_not_called()

        # Backlog full then cleared
        s3_output._add_to_backlog({"dummy": "event"}, "write_to_s3")
        s3_output._write_to_s3_resource()
        s3_output._write_document_batch.assert_called_once()
        assert self._calculate_backlog_size(s3_output) == 0

        # Backlog not full
        for idx in range(message_backlog_size - 1):
            s3_output._add_to_backlog({"dummy": "event"}, "write_to_s3")
            s3_output._write_to_s3_resource()
            assert self._calculate_backlog_size(s3_output) == idx + 1
        s3_output._write_document_batch.assert_called_once()

        # Backlog full then cleared
        s3_output._add_to_backlog({"dummy": "event"}, "write_to_s3")
        s3_output._write_to_s3_resource()
        assert s3_output._write_document_batch.call_count == 2
        assert self._calculate_backlog_size(s3_output) == 0

    def test_store_counts_processed_events(self):
        self.object._s3_resource = mock.MagicMock()
        super().test_store_counts_processed_events()

    def test_store_does_not_call_batch_finished_callback_if_disabled(self):
        s3_config = deepcopy(self.CONFIG)
        s3_config.update({"call_input_callback": False})
        s3_output = Factory.create({"s3": s3_config})
        s3_output._s3_resource = mock.MagicMock()
        s3_output.input_connector = mock.MagicMock()
        s3_output.store({"message": "my event message"})
        s3_output.input_connector.batch_finished_callback.assert_not_called()

    def test_write_to_s3_resource_replaces_dates(self):
        expected_prefix = f'base_prefix/prefix-{TimeParser.now().strftime("%y:%m:%d")}'
        self.object._write_backlog = mock.MagicMock()
        self.object._add_to_backlog({"foo": "bar"}, "base_prefix/prefix-%{%y:%m:%d}")
        self.object._write_to_s3_resource()
        resulting_prefix = next(iter(self.object._message_backlog.keys()))

        assert expected_prefix == resulting_prefix

    def test_message_backlog_is_not_written_if_message_backlog_size_not_reached(self):
        config = deepcopy(self.CONFIG)
        config.update({"message_backlog_size": 2})
        self.object = Factory.create({"s3": config})
        assert len(self.object._message_backlog) == 0
        with mock.patch(
            "logprep.connector.s3.output.S3Output._write_backlog"
        ) as mock_write_backlog:
            self.object.store({"test": "event"})
        mock_write_backlog.assert_not_called()

    def test_write_backlog_executed_on_empty_message_backlog(self):
        with mock.patch(
            "logprep.connector.s3.output.S3Output._backlog_size", new_callable=mock.PropertyMock
        ) as mock_backlog_size:
            self.object._write_backlog()
            mock_backlog_size.assert_not_called()

    def test_setup_registers_flush_timeout_tasks(self):
        job_count = len(self.object._scheduler.jobs)
        with pytest.raises(FatalOutputError):
            self.object.setup()
        assert len(self.object._scheduler.jobs) == job_count + 1

    @pytest.mark.parametrize(
        "error, message",
        [
            (
                EndpointConnectionError(endpoint_url="http://xdfzy:123"),
                r".*Could not connect to the endpoint URL.*",
            ),
            (
                ConnectionClosedError(endpoint_url="http://xdfzy:123"),
                r".*Connection was closed before we received a valid response from endpoint URL.*",
            ),
            (
                ClientError(error_response={"foo": "bar"}, operation_name="HeadBucket"),
                r".*An error occurred \(\w+\) when calling the HeadBucket operation: \w+.*",
            ),
            (
                BotoCoreError(),
                r".*An unspecified error occurred.*",
            ),
        ],
    )
    def test_setup_raises_fataloutputerror_if_boto_exception_is_raised(self, error, message):
        with mock.patch.object(
            self.object._s3_resource.meta.client,
            "head_bucket",
            side_effect=error,
        ):
            with pytest.raises(FatalOutputError, match=message):
                self.object.setup()

    @staticmethod
    def _calculate_backlog_size(s3_output):
        return sum(len(values) for values in s3_output._message_backlog.values())

    @mock.patch("logprep.connector.s3.output.S3Output._s3_resource", new=mock.MagicMock())
    @mock.patch("inspect.getmembers", return_value=[("mock_prop", lambda: None)])
    def test_setup_populates_cached_properties(self, mock_getmembers):
        self.object.setup()
        mock_getmembers.assert_called_with(self.object)

    @pytest.mark.skip(reason="Not implemented yet")
    def test_setup_calls_wait_for_health(self):
        pass
