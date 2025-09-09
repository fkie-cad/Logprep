# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=unnecessary-dunder-call
# pylint: disable=too-many-lines
# pylint: disable=unused-argument


import base64
import json
import os
import re
import zlib
from copy import deepcopy
from logging import getLogger
from unittest import mock

import pytest

from logprep.abc.connector import Connector
from logprep.factory import Factory
from logprep.ng.abc.input import CriticalInputError, Input, InputIterator
from logprep.ng.abc.output import Output
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.set_event_backlog import SetEventBacklog
from logprep.util.helper import get_dotted_field_value
from logprep.util.time import TimeParser
from tests.unit.component.base import BaseComponentTestCase


class BaseConnectorTestCase(BaseComponentTestCase):
    CONFIG: dict = {}
    object: Connector = None
    logger = getLogger()

    expected_metrics = [
        "logprep_processing_time_per_event",
        "logprep_number_of_processed_events",
        "logprep_number_of_warnings",
        "logprep_number_of_errors",
    ]

    def test_is_a_connector_implementation(self):
        assert isinstance(self.object, Connector)


class BaseInputTestCase(BaseConnectorTestCase):
    def check_input_registered_failed_event_with_message(
        self,
        connector: Connector,
        expected_error_message: str,
        expected_event_data: dict | None = None,
    ):
        """Helper method to reduce code duplication by checking if a failed event
        is registered to input connectors event backlog with expected error message."""

        if expected_event_data is None:
            expected_event_data = {}

        error_events = [
            error_event
            for error_event in connector.event_backlog.backlog
            if error_event.state.current_state is EventStateType.FAILED
        ]

        assert len(error_events) == 1

        failed_event = error_events[0]
        assert failed_event.data == expected_event_data
        assert len(failed_event.errors) == 1
        assert isinstance(failed_event.errors[0], CriticalInputError)
        assert failed_event.errors[0].message == expected_error_message

    def test_get_next_returns_event(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"message": "test message"}, b'{"message": "test message"}', None)

        with mock.patch.object(connector, "_get_event", return_value=return_value):
            event = connector.get_next(0.01)
            assert isinstance(event, LogEvent)

    def test_inputiterator_iter_is_self(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        input_iterator = InputIterator(input_connector=connector, timeout=0.01)
        assert input_iterator is iter(input_iterator)

    def test_is_input_instance(self):
        assert isinstance(self.object, Input)

    def test_add_hmac_returns_true_if_hmac_options(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config})
        assert connector._add_hmac is True

    def test_add_hmac_to_adds_hmac(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config})
        processed_event = connector._add_hmac_to({"message": "test message"}, b"test message")
        assert processed_event.get("Hmac")
        assert (
            processed_event.get("Hmac").get("hmac")
            == "cc67047535dc9ac17775785b05fe8cdd245387e2d036b2475e82f37653c5bf3d"
        )
        assert (
            processed_event.get("Hmac").get("compressed_base64") == "eJwrSS0uUchNLS5OTE8FAB8fBMY="
        )

    def test_add_hmac_to_adds_hmac_even_if_no_raw_message_was_given(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config})
        processed_event = connector._add_hmac_to({"message": "test message"}, None)
        assert processed_event.get("Hmac")
        calculated_hmac = processed_event.get("Hmac").get("hmac")
        assert (
            calculated_hmac == "8b2d75efcba66476e5551d44065128bacff2f090db5b08d7a0201c33e3f651f5"
        ), f"Wrong hmac: '{calculated_hmac}'"
        calculated_compression = processed_event.get("Hmac").get("compressed_base64")
        assert (
            calculated_compression == "eJyrVspNLS5OTE9VslIqSS0uUYBxawF+Fwll"
        ), f"Wrong compression: {calculated_compression}"

    def test_get_next_with_hmac_of_raw_message(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = {"message": "with_content"}

        raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(return_value.copy(), raw_encoded_test_event, None)
        )
        expected_event = LogEvent(
            data={
                "message": "with_content",
                "Hmac": {
                    "compressed_base64": "eJyrVspNLS5OTE9VslIqzyzJiE/OzytJzStRqgUAgKkJtg==",
                    "hmac": "dfe78753da634d7b76760488dbb2cf7bfe1b0e4e794930c36e98a984b6b6be63",
                },
            },
            original=b"",
        )
        connector_next_msg = connector.get_next(1)
        assert connector_next_msg == expected_event, "Output event with hmac is not as expected"

        decoded = base64.b64decode(connector_next_msg.data["Hmac"]["compressed_base64"])
        decoded_message = zlib.decompress(decoded)
        assert return_value == json.loads(
            decoded_message.decode("utf-8")
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_of_subfield(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "message.with_subfield",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = {"message": {"with_subfield": "content"}}

        raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(return_value.copy(), raw_encoded_test_event, None)
        )
        expected_event = LogEvent(
            data={
                "message": {"with_subfield": "content"},
                "Hmac": {
                    "compressed_base64": "eJxLzs8rSc0rAQALywL8",
                    "hmac": "e01e02a09cb270eebf7ae846b96d7306681038bd279f85d44c77019e0c4f6316",
                },
            },
            original=b"",
        )

        connector_next_msg = connector.get_next(1)
        assert connector_next_msg == expected_event

        decoded = base64.b64decode(connector_next_msg.data["Hmac"]["compressed_base64"])
        decoded_message = zlib.decompress(decoded)
        assert return_value["message"]["with_subfield"] == decoded_message.decode(
            "utf-8"
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_of_non_existing_subfield(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "non_existing_field",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = {"message": {"with_subfield": "content"}}

        raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(return_value.copy(), raw_encoded_test_event, None)
        )
        expected_error_message = "Couldn't find the hmac target field 'non_existing_field'"

        assert connector.get_next(1) is None
        assert len(connector.event_backlog.backlog) == 1

        subscriptable_event_backlog = list(connector.event_backlog.backlog)
        failed_event = subscriptable_event_backlog[0]
        assert failed_event.data["message"]["with_subfield"] == "content"
        assert failed_event.state.current_state == EventStateType.FAILED
        assert len(failed_event.errors) == 1
        assert isinstance(failed_event.errors[0], CriticalInputError)
        assert failed_event.errors[0].message == expected_error_message

    def test_get_next_with_hmac_result_in_dotted_subfield(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac.dotted.subfield",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = {"message": "with_content"}

        raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(return_value.copy(), raw_encoded_test_event, None)
        )
        expected_event = LogEvent(
            data={
                "message": "with_content",
                "Hmac": {
                    "dotted": {
                        "subfield": {
                            "compressed_base64": "eJyrVspNLS5OTE9VslIqzyzJiE/OzytJzStRqgUAgKkJtg==",
                            "hmac": "dfe78753da634d7b76760488dbb2cf7bfe1b0e4e794930c36e98a984b6b6be63",
                        }
                    }
                },
            },
            original=b"",
        )

        connector_next_msg = connector.get_next(1)
        assert connector_next_msg == expected_event
        decoded = base64.b64decode(
            connector_next_msg.data["Hmac"]["dotted"]["subfield"]["compressed_base64"]
        )
        decoded_message = zlib.decompress(decoded)
        assert return_value == json.loads(
            decoded_message.decode("utf-8")
        ), "The hmac base massage was not correctly encoded and compressed. "

    def test_get_next_with_hmac_result_in_already_existing_subfield(self):
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(
            {
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "message",
                    }
                }
            }
        )
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        test_event = {"message": {"with_subfield": "content"}}

        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(test_event.copy(), raw_encoded_test_event, None)
        )

        expected_error_message = (
            "FieldExistsWarning: The following fields could not be written, because one or "
            "more subfields existed and could not be extended: message, event={'message': "
            "{'with_subfield': 'content'}}"
        )

        assert connector.get_next(1) is None
        assert len(connector.event_backlog.backlog) == 1

        subscriptable_event_backlog = list(connector.event_backlog.backlog)
        failed_event = subscriptable_event_backlog[0]
        assert failed_event.data == test_event
        assert failed_event.state.current_state == EventStateType.FAILED
        assert len(failed_event.errors) == 1
        assert isinstance(failed_event.errors[0], CriticalInputError)
        assert failed_event.errors[0].message == expected_error_message

    def test_get_next_without_hmac(self):
        connector_config = deepcopy(self.CONFIG)
        assert not connector_config.get("preprocessing", {}).get("hmac")
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = {"message": "with_content"}

        raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
        connector._get_event = mock.MagicMock(
            return_value=(return_value.copy(), raw_encoded_test_event, None)
        )
        connector_next_msg = connector.get_next(1)
        assert connector_next_msg == LogEvent(data=return_value, original=b"")

    def test_preprocessing_version_info_is_added_if_configured(self):
        preprocessing_config = {
            "preprocessing": {
                "version_info_target_field": "version_info",
                "hmac": {"target": "", "key": "", "output_field": ""},
            },
            "version_information": {"logprep": "3.3.0", "configuration": "unset"},
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = {"any": "content"}

        connector._get_event = mock.MagicMock(return_value=(return_value, None, None))
        result = connector.get_next(0.01)
        assert result.data.get("version_info", {}).get("logprep") == "3.3.0"
        assert result.data.get("version_info", {}).get("configuration") == "unset"

    def test_pipeline_preprocessing_does_not_add_versions_if_target_field_exists_already(self):
        preprocessing_config = {
            "preprocessing": {
                "version_info_target_field": "version_info",
                "hmac": {"target": "", "key": "", "output_field": ""},
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        test_event = {"any": "content", "version_info": "something random"}

        connector._get_event = mock.MagicMock(return_value=(test_event, None, None))

        expected_error_message = (
            "FieldExistsWarning: The following fields could not be written, because one or "
            "more subfields existed and could not be extended: version_info, "
            "event={'any': 'content', 'version_info': 'something random'}"
        )

        assert connector.get_next(1) is None
        assert len(connector.event_backlog.backlog) == 1

        subscriptable_event_backlog = list(connector.event_backlog.backlog)
        failed_event = subscriptable_event_backlog[0]
        assert failed_event.data == test_event
        assert failed_event.state.current_state == EventStateType.FAILED
        assert len(failed_event.errors) == 1
        assert isinstance(failed_event.errors[0], CriticalInputError)
        assert failed_event.errors[0].message == expected_error_message

    def test_pipeline_preprocessing_only_version_information(self):
        preprocessing_config = {
            "preprocessing": {
                "version_info_target_field": "version_info",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        test_event = {"any": "content", "version_info": "something random"}

        connector._get_event = mock.MagicMock(return_value=(test_event, None, None))

        expected_error_message = (
            "FieldExistsWarning: The following fields could not be written, because one or "
            "more subfields existed and could not be extended: version_info, "
            "event={'any': 'content', 'version_info': 'something random'}"
        )

        assert connector.get_next(1) is None
        assert len(connector.event_backlog.backlog) == 1

        subscriptable_event_backlog = list(connector.event_backlog.backlog)
        failed_event = subscriptable_event_backlog[0]
        assert failed_event.data == test_event
        assert failed_event.state.current_state == EventStateType.FAILED
        assert len(failed_event.errors) == 1
        assert isinstance(failed_event.errors[0], CriticalInputError)
        assert failed_event.errors[0].message == expected_error_message

    def test_get_raw_event_is_callable(self):
        # should be overwritten for special implementation
        result = self.object._get_raw_event(0.001)
        assert result is None

    def test_connector_metrics_counts_processed_events(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"event:": "test_event"}, None, None)

        connector.metrics.number_of_processed_events = 0

        with mock.patch.object(connector, "_get_event", return_value=return_value):
            connector.get_next(0.01)

        assert connector.metrics.number_of_processed_events == 1

    def test_connector_metrics_does_not_count_if_no_event_was_retrieved(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        connector.metrics.number_of_processed_events = 0
        connector._get_event = mock.MagicMock(return_value=(None, None, None))
        connector.get_next(0.01)
        assert connector.metrics.number_of_processed_events == 0

    def test_get_next_adds_timestamp_if_configured(self):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "arrival_time",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"any": "content"}, None, None)

        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        target_field = preprocessing_config.get("preprocessing", {}).get(
            "log_arrival_time_target_field"
        )
        assert target_field in result.data
        assert isinstance(result.data[target_field], str)
        assert (
            TimeParser.now() - TimeParser.from_string(result.data[target_field])
        ).total_seconds() > 0

    def test_pipeline_preprocessing_does_not_add_log_arrival_time_if_target_field_exists_already(
        self,
    ):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "arrival_time",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        test_event = {"any": "content", "arrival_time": "does not matter"}

        connector._get_event = mock.MagicMock(return_value=(test_event, None, None))

        expected_error_message = (
            "FieldExistsWarning: The following fields could not be written, because one "
            "or more subfields existed and could not be extended: arrival_time, "
            "event={'any': 'content', 'arrival_time': 'does not matter'}"
        )

        assert connector.get_next(1) is None
        assert len(connector.event_backlog.backlog) == 1

        subscriptable_event_backlog = list(connector.event_backlog.backlog)
        failed_event = subscriptable_event_backlog[0]
        assert failed_event.data == test_event
        assert failed_event.state.current_state == EventStateType.FAILED
        assert len(failed_event.errors) == 1
        assert isinstance(failed_event.errors[0], CriticalInputError)
        assert failed_event.errors[0].message == expected_error_message

    def test_pipeline_preprocessing_add_log_arrival_time_if_target_parent_field_exists_already_and_is_dict(
        self,
    ):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "event.created",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = {"any": "content", "event": {"does not": "matter"}}

        connector._get_event = mock.MagicMock(return_value=(return_value, None, None))
        event = connector.get_next(0.01)
        time_value = get_dotted_field_value(event.data, "event.created")
        assert time_value
        iso8601_regex = (
            r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|([+-]\d{2}:\d{2})$)"
        )
        assert re.search(iso8601_regex, time_value)

    def test_pipeline_preprocessing_add_log_arrival_time_if_target_parent_field_exists_already_and_not_dict(
        self,
    ):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "event.created",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = {"any": "content", "event": "does not matter"}

        connector._get_event = mock.MagicMock(return_value=(return_value, None, None))
        event = connector.get_next(0.01)
        time_value = get_dotted_field_value(event.data, "event.created")
        assert time_value
        iso8601_regex = (
            r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|([+-]\d{2}:\d{2})$)"
        )
        assert re.search(iso8601_regex, time_value)
        original_event = get_dotted_field_value(event.data, "event.@original")
        assert original_event == "does not matter"

    def test_pipeline_preprocessing_adds_timestamp_delta_if_configured(self):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "arrival_time",
                "log_arrival_timedelta": {
                    "target_field": "log_arrival_timedelta",
                    "reference_field": "@timestamp",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = (
            {"any": "content", "@timestamp": "1999-09-09T09:09:09.448319+02:00"},
            None,
            None,
        )

        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        target_field = (
            preprocessing_config.get("preprocessing")
            .get("log_arrival_timedelta")
            .get("target_field")
        )
        assert target_field in result.data
        assert isinstance(result.data[target_field], float)

    def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_configured_but_reference_field_not_found(
        self,
    ):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "arrival_time",
                "log_arrival_timedelta": {
                    "target_field": "log_arrival_timedelta",
                    "reference_field": "@timestamp",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"any": "content"}, None, None)

        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        assert "arrival_time" in result.data
        assert "log_arrival_timedelta" not in result.data

    def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_not_configured(self):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_time_target_field": "arrival_time",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"any": "content"}, None, None)

        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        assert "arrival_time" in result.data

    def test_add_full_event_to_target_field_with_string_format(self):
        preprocessing_config = {
            "preprocessing": {
                "add_full_event_to_target_field": {
                    "format": "str",
                    "target_field": "event.original",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"any": "content"}, None, None)

        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        expected = {"event": {"original": '"{\\"any\\":\\"content\\"}"'}}
        assert result.data == expected, f"{expected} is not the same as {result.data}"

    def test_add_full_event_to_targetfield_with_same_name(self):
        preprocessing_config = {
            "preprocessing": {
                "add_full_event_to_target_field": {
                    "format": "str",
                    "target_field": "any.content",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"any": "content"}, None, None)

        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        expected = {"any": {"content": '"{\\"any\\":\\"content\\"}"'}}
        assert result.data == expected, f"{expected} is not the same as {result.data}"

    def test_add_full_event_to_targetfield_vs_version_info_target(self):
        preprocessing_config = {
            "preprocessing": {
                "add_full_event_to_target_field": {
                    "format": "str",
                    "target_field": "any.content",
                },
                "version_info_target_field": "version_info",
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"any": "content"}, None, None)

        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        expected = {
            "any": {"content": '"{\\"any\\":\\"content\\"}"'},
            "version_info": {"logprep": "", "configuration": ""},
        }
        assert result.data == expected, f"{expected} is not the same as {result.data}"

    def test_add_full_event_to_target_field_with_dict_format(self):
        preprocessing_config = {
            "preprocessing": {
                "add_full_event_to_target_field": {
                    "format": "dict",
                    "target_field": "event.original",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"any": "content"}, None, None)

        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        expected = {"event": {"original": {"any": "content"}}}
        assert result.data == expected, f"{expected} is not the same as {result.data}"

    def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_configured_but_log_arrival_timestamp_not(
        self,
    ):
        preprocessing_config = {
            "preprocessing": {
                "log_arrival_timedelta": {
                    "target_field": "log_arrival_timedelta",
                    "reference_field": "@timestamp",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"any": "content"}, None, None)

        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        assert result.data == {"any": "content"}

    def test_preprocessing_enriches_by_multiple_env_variables(self):
        preprocessing_config = {
            "preprocessing": {
                "enrich_by_env_variables": {
                    "enriched_field1": "TEST_ENV_VARIABLE_FOO",
                    "enriched_field2": "TEST_ENV_VARIABLE_BAR",
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"any": "content"}, None, None)

        os.environ["TEST_ENV_VARIABLE_FOO"] = "test_value_foo"
        os.environ["TEST_ENV_VARIABLE_BAR"] = "test_value_bar"
        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        assert result.data == {
            "any": "content",
            "enriched_field1": "test_value_foo",
            "enriched_field2": "test_value_bar",
        }

    def test_get_next_counts_number_of_processed_events(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"message": "test message"}, b'{"message": "test message"}', None)

        connector._get_event = mock.MagicMock(return_value=return_value)
        connector.metrics.number_of_processed_events = 0
        connector.get_next(0.01)

        assert connector.metrics.number_of_processed_events == 1

    def test_get_next_does_not_count_number_of_processed_events_if_event_is_none(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        connector.metrics.number_of_processed_events = 0
        connector._get_event = mock.MagicMock(return_value=(None, None, None))
        connector.get_next(0.01)
        assert connector.metrics.number_of_processed_events == 0

    def test_get_next_has_time_measurement(self):
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"message": "test message"}, b'{"message": "test message"}', None)

        mock_metric = mock.MagicMock()
        connector.metrics.processing_time_per_event = mock_metric
        connector._get_event = mock.MagicMock(return_value=return_value)
        connector.get_next(0.01)
        assert isinstance(connector.metrics.processing_time_per_event, mock.MagicMock)
        # asserts entering context manager in metrics.metrics.Metric.measure_time
        mock_metric.assert_has_calls([mock.call.tracker.labels().time().__enter__()])

    def test_input_iterator(self):
        batch_events = [
            {"valid": "json_1"},
            {"valid": "json_2"},
            {"valid": "json_3"},
        ]

        def get_next_mock(*args, **kwargs):
            if batch_events:
                return batch_events.pop(0)
            return None

        with mock.patch.object(self.object, "get_next", new=get_next_mock):
            input_iterator = self.object(timeout=0.001)
            assert next(input_iterator) == {"valid": "json_1"}
            assert next(input_iterator) == {"valid": "json_2"}
            assert next(input_iterator) == {"valid": "json_3"}
            assert next(input_iterator) is None

    def test_add_full_event_to_target_field_without_clear(self):
        preprocessing_config = {
            "preprocessing": {
                "add_full_event_to_target_field": {
                    "format": "str",
                    "target_field": "event.original",
                    "clear_event": False,
                },
            }
        }
        connector_config = deepcopy(self.CONFIG)
        connector_config.update(preprocessing_config)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        return_value = ({"any": "content"}, None, None)

        connector._get_event = mock.MagicMock(return_value=return_value)
        result = connector.get_next(0.01)
        expected = {"any": "content", "event": {"original": '"{\\"any\\":\\"content\\"}"'}}
        assert result.data == expected, f"{expected} is not the same as {result.data}"

    @pytest.mark.parametrize(
        "states, new_size, expected_message",
        [
            (
                (EventStateType.ACKED, EventStateType.PROCESSING),
                2,
                "expecting: 1*ACKED will be removed from backlog",
            ),
            (
                (EventStateType.ACKED, EventStateType.PROCESSING, EventStateType.ACKED),
                2,
                "expecting: 2*ACKED will be removed from backlog",
            ),
            (
                (EventStateType.PROCESSING, EventStateType.PROCESSING),
                3,
                "expecting: no event state will be changed",
            ),
            (
                (EventStateType.DELIVERED, EventStateType.DELIVERED),
                3,
                "expecting: 2*DELIVERED should switch to ACKED (both events)",
            ),
        ],
    )
    def test_acknowledge_events(self, states, new_size, expected_message):
        backlog = {
            LogEvent(data={"message": f"msg {i + 1}"}, original=b"", state=s)
            for i, s in enumerate(states, start=1)
        }
        initial_size = len(backlog)
        connector_config = deepcopy(self.CONFIG)
        connector = Factory.create({"test connector": connector_config})
        connector._wait_for_health = mock.MagicMock()
        connector.pipeline_index = 1

        set_event_backlog = SetEventBacklog()
        set_event_backlog.backlog = backlog

        with (
            mock.patch.object(connector, "event_backlog", new=set_event_backlog),
            mock.patch.object(
                connector,
                "_get_event",
                return_value=({"message": "another test message"}, b"", None),
            ),
        ):
            assert len(connector.event_backlog.backlog) == initial_size, expected_message
            _ = connector.get_next(0.01)
            assert len(connector.event_backlog.backlog) == new_size, expected_message


class BaseOutputTestCase(BaseConnectorTestCase):
    def test_is_output_instance(self):
        assert isinstance(self.object, Output)

    def test_store_counts_processed_events(self):
        self.object.metrics.number_of_processed_events = 0
        event = LogEvent({"message": "my event message"}, original=b"")
        self.object.store(event)
        assert self.object.metrics.number_of_processed_events == 1

    def test_store_changes_state_successful_path(self):
        """This test is a placeholder for the successful path of the store method.
        you have to override this method in some output implementations depending on the
        implementation of the store and write_backlog methods.
        In simple implementations, the next_state method of the event is called twice and the result
        is the DELIVERED state.
        In more complex implementations, the next_state method is called once and the store method and
        a second time in the write_backlog method.
        """
        state, expected_state = EventStateType.PROCESSED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )
        self.object.store(event)
        assert event.state == expected_state

    def test_store_changes_state_failed_event_with_unsuccessful_path(self):
        """This test is a placeholder for the successful path of the store method.
        you have to override this method in some output implementations depending on the
        implementation of the store and write_backlog methods.
        In simple implementations, the next_state method of the event is called twice and the result
        is the DELIVERED state.
        In more complex implementations, the next_state method is called once and the store method and
        a second time in the write_backlog method.
        """
        state, expected_state = EventStateType.FAILED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )
        self.object.store(event)
        assert event.state == expected_state

    def test_store_custom_changes_state_successful_path(self):
        """This test is a placeholder for the successful path of the store method.
        you have to override this method in some output implementations depending on the
        implementation of the store and write_backlog methods.
        In simple implementations, the next_state method of the event is called twice and the result
        is the DELIVERED state.
        In more complex implementations, the next_state method is called once and the store method and
        a second time in the write_backlog method.
        """
        state, expected_state = EventStateType.PROCESSED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )
        self.object.store_custom(event, "stderr")
        assert event.state == expected_state, f"{state=}, {expected_state=}, {event.state=} "

    def test_store_custom_changes_state_failed_event_with_unsuccessful_path(self):
        """This test is a placeholder for the successful path of the store method.
        you have to override this method in some output implementations depending on the
        implementation of the store and write_backlog methods.
        In simple implementations, the next_state method of the event is called twice and the result
        is the DELIVERED state.
        In more complex implementations, the next_state method is called once and the store method and
        a second time in the write_backlog method.
        """
        state, expected_state = EventStateType.FAILED, EventStateType.DELIVERED
        event = LogEvent(
            {"message": "test message"},
            original=b"",
            state=state,
        )
        self.object.store_custom(event, "stderr")
        assert event.state == expected_state, f"{state=}, {expected_state=}, {event.state=} "

    def test_store_handles_errors(self):
        """you have to override this method in some output implementations depending on the implementation of the store and write_backlog methods."""
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        # implement mocking for target connector here
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

    def test_store_custom_handles_errors(self):
        """you have to override this method in some output implementations depending on the implementation of the store and write_backlog methods."""
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.PROCESSED)
        # implement mocking for target connector here
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED, f"{event.state} should be FAILED"

    def test_store_handles_errors_failed_event(self):
        """you have to override this method in some output implementations depending on the implementation of the store and write_backlog methods."""
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.FAILED)
        # implement mocking for target connector start
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED

    def test_store_custom_handles_errors_failed_event(self):
        """you have to override this method in some output implementations depending on the implementation of the store and write_backlog methods."""
        self.object.metrics.number_of_errors = 0
        event = LogEvent({"message": "test message"}, original=b"", state=EventStateType.FAILED)
        # implement mocking for target connector start
        assert self.object.metrics.number_of_errors == 1
        assert len(event.errors) == 1
        assert event.state == EventStateType.FAILED, f"{event.state} should be FAILED"

    def test_shutdown_flushes_output(self):
        with mock.patch(
            f"{self.object.__module__}.{self.object.__class__.__name__}.flush"
        ) as mock_flush:
            self.object.shut_down()
            mock_flush.assert_called_once()
