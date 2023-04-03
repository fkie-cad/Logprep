# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
# pylint: disable=attribute-defined-outside-init
import re
from copy import deepcopy
from time import sleep

import pytest
from datetime import datetime
from math import isclose
from unittest import mock

from botocore.exceptions import (
    EndpointConnectionError,
    ConnectionClosedError,
    ClientError,
    BotoCoreError,
)

import arrow

from logprep.factory import Factory
from tests.unit.connector.base import BaseOutputTestCase


class NotJsonSerializableMock:
    pass


class TestS3Output(BaseOutputTestCase):
    CONFIG = {
        "type": "s3_output",
        "endpoint_url": "http://host:123",
        "aws_access_key_id": "foo_aws_access_key_id",
        "aws_secret_access_key": "foo_aws_secret_access_key",
        "bucket": "foo_bucket",
        "default_prefix": "foo_default_prefix",
        "prefix_field": "foo_prefix_field",
        "error_prefix": "foo_error_prefix",
        "message_backlog_size": 1,
    }

    def test_describe_returns_s3_output(self):
        assert (
            self.object.describe() == "S3Output (Test Instance Name) - S3 Output: http://host:123"
        )

    def test_store_sends_with_default_prefix(self):
        event = {"field": "content"}
        expected = {
            "foo_default_prefix": [
                {
                    "message": '{"field": "content"}',
                    "reason": "Prefix field 'foo_prefix_field' empty or missing in document",
                }
            ]
        }
        s3_config = deepcopy(self.CONFIG)
        s3_config.update({"message_backlog_size": 2})
        s3_output = Factory.create({"s3": s3_config}, self.logger)

        s3_output.store(event)

        assert "foo_default_prefix" in s3_output._message_backlog
        assert len(s3_output._message_backlog["foo_default_prefix"]) == 1
        assert "@timestamp" in s3_output._message_backlog["foo_default_prefix"][0]
        assert s3_output._message_backlog["foo_default_prefix"][0].pop("@timestamp")
        assert s3_output._message_backlog == expected

    def test_store_sends_event_to_with_expected_prefix_if_prefix_missing_in_event(self):
        event = {"field": "content"}
        default_prefix = "default_prefix"
        expected = {
            "message": '{"field": "content"}',
            "reason": "Prefix field 'foo_prefix_field' empty or missing in document",
        }
        s3_config = deepcopy(self.CONFIG)
        s3_config.update({"default_prefix": default_prefix, "message_backlog_size": 2})
        s3_output = Factory.create({"s3": s3_config}, self.logger)

        s3_output.store(event)

        assert s3_output._message_backlog[default_prefix][0].pop("@timestamp")
        assert s3_output._message_backlog[default_prefix][0] == expected

    def test_store_custom_writes_event_with_expected_prefix(self):
        custom_prefix = "custom_prefix"
        event = {"field": "content"}
        expected = {"field": "content"}

        s3_config = deepcopy(self.CONFIG)
        s3_config.update({"message_backlog_size": 2})
        s3_output = Factory.create({"s3": s3_config}, self.logger)

        s3_output.store_custom(event, custom_prefix)
        assert s3_output._message_backlog[custom_prefix][0] == expected

    def test_store_failed(self):
        error_prefix = "error_prefix"
        event_received = {"field": "received"}
        event = {"field": "content"}
        error_message = "error message"
        expected = {
            "error": error_message,
            "original": event_received,
            "processed": event,
            "@timestamp": str(datetime.now()),
        }
        s3_config = deepcopy(self.CONFIG)
        s3_config.update({"error_prefix": error_prefix, "message_backlog_size": 2})
        s3_output = Factory.create({"s3": s3_config}, self.logger)

        s3_output.store_failed(error_message, event_received, event)

        print(s3_output._message_backlog)
        error_document = s3_output._message_backlog[error_prefix][0]
        # timestamp is compared to be approximately the same,
        # since it is variable and then removed to compare the rest
        error_time = datetime.timestamp(arrow.get(error_document["@timestamp"]).datetime)
        expected_time = datetime.timestamp(arrow.get(error_document["@timestamp"]).datetime)
        assert isclose(error_time, expected_time)
        del error_document["@timestamp"]
        del expected["@timestamp"]

        assert error_document == expected

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
                r"Could not connect to the endpoint URL$",
            ),
            (
                ConnectionClosedError(endpoint_url="foo"),
                r"Connection was closed before we received a valid response from endpoint URL$",
            ),
            (
                ClientError(error_response={"foo": "bar"}, operation_name="foo"),
                r"An error occurred \(\w+\) when calling the foo operation: \w+$",
            ),
            (
                BotoCoreError(),
                r"An unspecified error occurred",
            ),
        ],
    )
    def test_write_document_batch_calls_handles_errors(self, error, message):
        self.object._logger.warning = mock.MagicMock()
        with mock.patch(
            "logprep.connector.s3.output.S3Output._write_to_s3",
            side_effect=error,
        ):
            self.object._write_document_batch({"dummy": "event"}, "dummy_identifier")
        args, _ = self.object._logger.warning.call_args
        assert re.search(message, args[0])

    def test_write_to_s3_resource_sets_current_backlog_count_and_below_max_backlog(self):
        s3_config = deepcopy(self.CONFIG)
        message_backlog_size = 5
        s3_config.update({"message_backlog_size": message_backlog_size})
        s3_output = Factory.create({"s3": s3_config}, self.logger)
        assert s3_output._current_backlog_count == 0
        for idx in range(1, message_backlog_size):
            s3_output._write_to_s3_resource({"dummy": "event"}, "write_to_s3")
            assert s3_output._current_backlog_count == idx

    def test_write_to_s3_resource_sets_current_backlog_count_and_is_max_backlog(self):
        s3_config = deepcopy(self.CONFIG)
        message_backlog_size = 5
        s3_config.update({"message_backlog_size": message_backlog_size})
        s3_output = Factory.create({"s3": s3_config}, self.logger)

        s3_output._write_document_batch = mock.MagicMock()
        s3_output._write_document_batch.assert_not_called()

        # Backlog not full
        for idx in range(message_backlog_size - 1):
            s3_output._write_to_s3_resource({"dummy": "event"}, "write_to_s3")
            sleep(0.1)  # nosemgrep
            assert s3_output._current_backlog_count == idx + 1
        s3_output._write_document_batch.assert_not_called()

        # Backlog full then cleared
        s3_output._write_to_s3_resource({"dummy": "event"}, "write_to_s3")
        sleep(0.1)  # nosemgrep
        s3_output._write_document_batch.assert_called_once()
        assert s3_output._current_backlog_count == 0

        # Backlog not full
        for idx in range(message_backlog_size - 1):
            s3_output._write_to_s3_resource({"dummy": "event"}, "write_to_s3")
            sleep(0.1)  # nosemgrep
            assert s3_output._current_backlog_count == idx + 1
        s3_output._write_document_batch.assert_called_once()

        # Backlog full then cleared
        s3_output._write_to_s3_resource({"dummy": "event"}, "write_to_s3")
        sleep(0.1)  # nosemgrep
        assert s3_output._write_document_batch.call_count == 2
        assert s3_output._current_backlog_count == 0

    def test_store_counts_processed_events(self):
        self.object._s3_resource = mock.MagicMock()
        super().test_store_counts_processed_events()

    def test_store_calls_batch_finished_callback(self):
        self.object._s3_resource = mock.MagicMock()
        super().test_store_calls_batch_finished_callback()

    def test_store_does_not_call_batch_finished_callback_if_disabled(self):
        s3_config = deepcopy(self.CONFIG)
        s3_config.update({"call_input_callback": False})
        s3_output = Factory.create({"s3": s3_config}, self.logger)
        s3_output._s3_resource = mock.MagicMock()
        s3_output.input_connector = mock.MagicMock()
        s3_output.store({"message": "my event message"})
        s3_output.input_connector.batch_finished_callback.assert_not_called()