# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
# pylint: disable=unnecessary-lambda-assignment
# pylint: disable=unnecessary-dunder-call
# pylint: disable=line-too-long

import base64
import json
import os
import re
import zlib
from copy import deepcopy
from itertools import cycle
from unittest import mock

import pytest

from logprep.factory import Factory
from logprep.ng.abc.input import CriticalInputError, SourceDisconnectedWarning
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.set_event_backlog import SetEventBacklog
from logprep.util.time import TimeParser
from tests.unit.ng.connector.base import BaseInputTestCase


class TestJsonInput(BaseInputTestCase):
    timeout = 0.1

    CONFIG = {"type": "ng_json_input", "documents_path": "/does/not/matter"}

    @pytest.fixture
    def mock_parse(self):
        with mock.patch("logprep.ng.connector.json.input.parse_json") as _mock_parse:
            yield _mock_parse

    def patch_documents_property(self, *, document):
        """
        Patch the `@cached_property` `_documents` to return a shared, mutable list.

        If `document` is a list, returns the same mutable list every time.
        If `document` is a callable, uses it as side_effect.
        """
        if callable(document):
            side_effect = document
        else:
            shared_list = list(document)  # make a real mutable copy
            side_effect = lambda: shared_list

        return mock.patch(
            "logprep.ng.connector.json.input.JsonInput._documents",
            new_callable=mock.PropertyMock,
            side_effect=side_effect,
        )

    def test_documents_returns(self):
        return_value = [{"message": "test_message"}]

        with self.patch_documents_property(document=return_value):
            config = deepcopy(self.CONFIG)
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            assert connector._documents == return_value

    def test_get_next_returns_event(self):
        return_value = ({"message": "test message"}, b'{"message": "test message"}', None)

        with self.patch_documents_property(document=return_value):
            connector_config = deepcopy(self.CONFIG)
            connector = Factory.create({"test connector": connector_config})
            connector._wait_for_health = mock.MagicMock()
            connector.pipeline_index = 1
            connector.setup()

            with mock.patch.object(connector, "_get_event", return_value=return_value):
                event = connector.get_next(0.01)
                assert isinstance(event, LogEvent)

    def test_get_next_returns_document(self):
        return_value = [{"message": "test_message"}]

        with self.patch_documents_property(document=return_value):
            expected = return_value[0]

            config = deepcopy(self.CONFIG)
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            document = connector.get_next(self.timeout)
            assert document.data == expected

    def test_get_next_returns_multiple_documents(self):
        return_value = [{"order": 0}, {"order": 1}]

        with self.patch_documents_property(document=return_value):
            config = deepcopy(self.CONFIG)
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            event = connector.get_next(self.timeout)
            assert {"order": 0} == event.data
            event = connector.get_next(self.timeout)
            assert {"order": 1} == event.data

    def test_get_next_with_hmac_of_raw_message(self):
        return_value = {"message": "with_content"}

        with self.patch_documents_property(document=return_value):
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
            connector.setup()

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

    def test_get_next_with_hmac_of_non_existing_subfield(self):
        return_value = {"message": {"with_subfield": "content"}}

        with self.patch_documents_property(document=return_value):
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
            connector.setup()

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

    def test_get_next_with_hmac_of_subfield(self):
        return_value = {"message": {"with_subfield": "content"}}

        with self.patch_documents_property(document=return_value):
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
            connector.setup()

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

    def test_get_next_with_hmac_result_in_dotted_subfield(self):
        return_value = {"message": "with_content"}

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
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
        test_event = {"message": {"with_subfield": "content"}}

        with self.patch_documents_property(document=test_event):
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
            connector.setup()

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
        return_value = {"message": "with_content"}

        with self.patch_documents_property(document=return_value):
            connector_config = deepcopy(self.CONFIG)
            assert not connector_config.get("preprocessing", {}).get("hmac")
            connector = Factory.create({"test connector": connector_config})
            connector._wait_for_health = mock.MagicMock()
            connector.pipeline_index = 1
            connector.setup()
            raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
            connector._get_event = mock.MagicMock(
                return_value=(return_value.copy(), raw_encoded_test_event, None)
            )
            connector_next_msg = connector.get_next(1)
            assert connector_next_msg == LogEvent(data=return_value, original=b"")

    def test_preprocessing_version_info_is_added_if_configured(self):
        return_value = {"any": "content"}

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=(return_value, None, None))
            result = connector.get_next(0.01)
            assert result.data.get("version_info", {}).get("logprep") == "3.3.0"
            assert result.data.get("version_info", {}).get("configuration") == "unset"

    def test_pipeline_preprocessing_does_not_add_versions_if_target_field_exists_already(self):
        test_event = {"any": "content", "version_info": "something random"}

        with self.patch_documents_property(document=test_event):
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
            connector.setup()
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
        test_event = {"any": "content", "version_info": "something random"}

        with self.patch_documents_property(document=test_event):
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
            connector.setup()

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

    def test_connector_metrics_counts_processed_events(self):
        return_value = ({"event:": "test_event"}, None, None)

        with self.patch_documents_property(document=return_value):
            connector_config = deepcopy(self.CONFIG)
            connector = Factory.create({"test connector": connector_config})
            connector._wait_for_health = mock.MagicMock()
            connector.pipeline_index = 1
            connector.setup()

            connector.metrics.number_of_processed_events = 0

            with mock.patch.object(connector, "_get_event", return_value=return_value):
                connector.get_next(0.01)

            assert connector.metrics.number_of_processed_events == 1

    def test_get_next_adds_timestamp_if_configured(self):
        return_value = ({"any": "content"}, None, None)

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
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
        test_event = {"any": "content", "arrival_time": "does not matter"}

        with self.patch_documents_property(document=test_event):
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
            connector.setup()
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
        return_value = {"any": "content", "event": {"does not": "matter"}}

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=(return_value, None, None))
            event = connector.get_next(0.01)
            time_value = event.get_dotted_field_value("event.created")
            assert time_value
            iso8601_regex = (
                r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|([+-]\d{2}:\d{2})$)"
            )
            assert re.search(iso8601_regex, time_value)

    def test_pipeline_preprocessing_add_log_arrival_time_if_target_parent_field_exists_already_and_not_dict(
        self,
    ):
        return_value = {"any": "content", "event": "does not matter"}

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=(return_value, None, None))
            event = connector.get_next(0.01)
            time_value = event.get_dotted_field_value("event.created")
            assert time_value
            iso8601_regex = (
                r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|([+-]\d{2}:\d{2})$)"
            )
            assert re.search(iso8601_regex, time_value)
            original_event = event.get_dotted_field_value("event.@original")
            assert original_event == "does not matter"

    def test_pipeline_preprocessing_adds_timestamp_delta_if_configured(self):
        return_value = (
            {"any": "content", "@timestamp": "1999-09-09T09:09:09.448319+02:00"},
            None,
            None,
        )

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
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
        return_value = ({"any": "content"}, None, None)

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=return_value)
            result = connector.get_next(0.01)
            assert "arrival_time" in result.data
            assert "log_arrival_timedelta" not in result.data

    def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_not_configured(self):
        return_value = ({"any": "content"}, None, None)

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=return_value)
            result = connector.get_next(0.01)
            assert "arrival_time" in result.data

    def test_add_full_event_to_target_field_with_string_format(self):
        return_value = ({"any": "content"}, None, None)

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=return_value)
            result = connector.get_next(0.01)
            expected = {"event": {"original": '"{\\"any\\":\\"content\\"}"'}}
            assert result.data == expected, f"{expected} is not the same as {result.data}"

    def test_add_full_event_to_targetfield_with_same_name(self):
        return_value = ({"any": "content"}, None, None)

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=return_value)
            result = connector.get_next(0.01)
            expected = {"any": {"content": '"{\\"any\\":\\"content\\"}"'}}
            assert result.data == expected, f"{expected} is not the same as {result.data}"

    def test_add_full_event_to_targetfield_vs_version_info_target(self):
        return_value = ({"any": "content"}, None, None)

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=return_value)
            result = connector.get_next(0.01)
            expected = {
                "any": {"content": '"{\\"any\\":\\"content\\"}"'},
                "version_info": {"logprep": "", "configuration": ""},
            }
            assert result.data == expected, f"{expected} is not the same as {result.data}"

    def test_add_full_event_to_target_field_with_dict_format(self):
        return_value = ({"any": "content"}, None, None)

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=return_value)
            result = connector.get_next(0.01)
            expected = {"event": {"original": {"any": "content"}}}
            assert result.data == expected, f"{expected} is not the same as {result.data}"

    def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_configured_but_log_arrival_timestamp_not(
        self,
    ):
        return_value = ({"any": "content"}, None, None)

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=return_value)
            result = connector.get_next(0.01)
            assert result.data == {"any": "content"}

    @pytest.mark.parametrize(
        ["timestamp", "expected_error_message"],
        [
            # Python version depending: "year 0 is out of range" = <py3.14 | "year must be in 1..9999" = >=py3.14
            ("0000-00-00 00:00:00", "(year 0 is out of range)|(year must be in 1..9999)"),
            ("invalid", "Invalid isoformat string: 'invalid'"),
        ],
    )
    def test_pipeline_preprocessing_timeparser_invalid_timestamp(
        self, timestamp, expected_error_message
    ):
        test_event = {"any": "content", "@timestamp": timestamp}

        with self.patch_documents_property(document=test_event):
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
            connector.setup()

            connector._get_event = mock.MagicMock(return_value=(test_event, None, None))

            assert connector.get_next(0.01) is None
            assert len(connector.event_backlog.backlog) == 1

            failed_event = list(connector.event_backlog.backlog)[0]
            assert len(failed_event.errors) == 1
            assert re.match(expected_error_message, failed_event.errors[0].message)

    def test_preprocessing_enriches_by_multiple_env_variables(self):
        return_value = ({"any": "content"}, None, None)

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
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
        return_value = ({"message": "test message"}, b'{"message": "test message"}', None)

        with self.patch_documents_property(document=return_value):
            connector_config = deepcopy(self.CONFIG)
            connector = Factory.create({"test connector": connector_config})
            connector._wait_for_health = mock.MagicMock()
            connector.pipeline_index = 1
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=return_value)
            connector.metrics.number_of_processed_events = 0
            connector.get_next(0.01)

            assert connector.metrics.number_of_processed_events == 1

    def test_get_next_has_time_measurement(self):
        return_value = ({"message": "test message"}, b'{"message": "test message"}', None)

        with self.patch_documents_property(document=return_value):
            connector_config = deepcopy(self.CONFIG)
            connector = Factory.create({"test connector": connector_config})
            connector._wait_for_health = mock.MagicMock()
            connector.pipeline_index = 1
            connector.setup()
            mock_metric = mock.MagicMock()
            connector.metrics.processing_time_per_event = mock_metric
            connector._get_event = mock.MagicMock(return_value=return_value)
            connector.get_next(0.01)
            assert isinstance(connector.metrics.processing_time_per_event, mock.MagicMock)
            # asserts entering context manager in metrics.metrics.Metric.measure_time
            mock_metric.assert_has_calls([mock.call.tracker.labels().time().__enter__()])

    def test_raises_exception_if_not_a_dict(self):
        return_value = ["no dict"]

        with self.patch_documents_property(document=return_value):
            config = deepcopy(self.CONFIG)
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            assert connector.get_next(1) is None

            self.check_input_registered_failed_event_with_message(
                connector=connector,
                expected_error_message="not a dict",
            )

    def test_raises_exception_if_one_element_is_not_a_dict(self):
        return_value = [{"order": 0}, "not a dict", {"order": 1}]

        with self.patch_documents_property(document=return_value):
            config = deepcopy(self.CONFIG)
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            assert isinstance(connector.get_next(self.timeout), LogEvent)
            assert connector.get_next(self.timeout) is None
            assert isinstance(connector.get_next(self.timeout), LogEvent)

            self.check_input_registered_failed_event_with_message(
                connector=connector,
                expected_error_message="not a dict",
            )

    def test_repeat_documents_repeats_documents(self):
        class CycledPopList:
            def __init__(self, iterable):
                self._iter = cycle(iterable)

            def pop(self, index=None):
                if index != 0:
                    raise IndexError("Only pop(0) supported in CycledPopList mock")
                return next(self._iter)

        cycled_list = CycledPopList([{"order": 0}, {"order": 1}, {"order": 2}])

        with mock.patch(
            "logprep.ng.connector.json.input.JsonInput._documents",
            new=mock.PropertyMock(return_value=cycled_list),
        ):
            config = deepcopy(self.CONFIG)
            config["repeat_documents"] = True
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            with mock.patch.dict(connector.__dict__, {"_documents": None}):
                for order in range(0, 9):
                    event = connector.get_next(self.timeout)
                    assert event.data.get("order") == order % 3

    @pytest.mark.skip(reason="not implemented")
    def test_setup_calls_wait_for_health(self):
        pass

    def test_json_input_iterator(self):
        return_value = [{"order": 0}, {"order": 1}, {"order": 2}]

        with self.patch_documents_property(document=return_value):
            config = deepcopy(self.CONFIG)
            config["repeat_documents"] = False
            json_input_connector = Factory.create(configuration={"Test Instance Name": config})
            json_input_connector.setup()

            json_input_iterator = json_input_connector(timeout=self.timeout)
            assert next(json_input_iterator).data == {"order": 0}
            assert next(json_input_iterator).data == {"order": 1}
            assert next(json_input_iterator).data == {"order": 2}

            with pytest.raises(SourceDisconnectedWarning):
                next(json_input_iterator)

    def test_connector_metrics_does_not_count_if_no_event_was_retrieved(self):
        with self.patch_documents_property(document={}):
            connector_config = deepcopy(self.CONFIG)
            connector = Factory.create({"test connector": connector_config})
            connector._wait_for_health = mock.MagicMock()
            connector.pipeline_index = 1
            connector.setup()

            connector.metrics.number_of_processed_events = 0
            connector._get_event = mock.MagicMock(return_value=(None, None, None))
            connector.get_next(0.01)
            assert connector.metrics.number_of_processed_events == 0

    def test_get_next_does_not_count_number_of_processed_events_if_event_is_none(self):
        with self.patch_documents_property(document={}):
            connector_config = deepcopy(self.CONFIG)
            connector = Factory.create({"test connector": connector_config})
            connector._wait_for_health = mock.MagicMock()
            connector.pipeline_index = 1
            connector.setup()

            connector.metrics.number_of_processed_events = 0
            connector._get_event = mock.MagicMock(return_value=(None, None, None))
            connector.get_next(0.01)
            assert connector.metrics.number_of_processed_events == 0

    def test_add_full_event_to_target_field_without_clear(self):
        return_value = ({"any": "content"}, None, None)

        with self.patch_documents_property(document=return_value):
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
            connector.setup()
            connector._get_event = mock.MagicMock(return_value=return_value)
            result = connector.get_next(0.01)
            expected = {"event": {"original": '"{\\"any\\":\\"content\\"}"'}}
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
        with self.patch_documents_property(document={}):
            backlog = {
                LogEvent(data={"message": f"msg {i + 1}"}, original=b"", state=s)
                for i, s in enumerate(states, start=1)
            }
            initial_size = len(backlog)
            connector_config = deepcopy(self.CONFIG)
            connector = Factory.create({"test connector": connector_config})
            connector._wait_for_health = mock.MagicMock()
            connector.pipeline_index = 1
            connector.setup()

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

            connector.shut_down()

    @pytest.mark.usefixtures("mock_parse")
    def test_job_cleanup_on_shutdown(self, component_scheduler):
        return super().test_job_cleanup_on_shutdown(component_scheduler)
