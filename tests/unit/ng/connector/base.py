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
import typing
import zlib
from abc import abstractmethod
from collections.abc import AsyncIterator, Callable, Sequence
from logging import getLogger
from unittest import mock

import pytest

from logprep.ng.abc.connector import Connector
from logprep.ng.abc.event import ErrorEvent, InputMeta, LogEvent, OutputEvent
from logprep.ng.abc.input import Input
from logprep.ng.abc.output import Output
from logprep.util.helper import FieldValue, get_dotted_field_value
from logprep.util.time import TimeParser
from tests.unit.ng.component.base import BaseComponentTestCase

ConnectorTypeT = typing.TypeVar("ConnectorTypeT", bound=Connector)
InputTypeT = typing.TypeVar("InputTypeT", bound=Input)
OutputTypeT = typing.TypeVar("OutputTypeT", bound=Output)


class BaseConnectorTestCase(BaseComponentTestCase[ConnectorTypeT], typing.Generic[ConnectorTypeT]):
    CONFIG: dict = {}
    logger = getLogger()

    expected_metrics = [
        "logprep_processing_time_per_event",
        "logprep_number_of_processed_events",
        "logprep_number_of_warnings",
        "logprep_number_of_errors",
    ]

    async def test_component_is_connector(self):
        assert isinstance(self.object, Connector)


class BaseInputTestCase(BaseConnectorTestCase[InputTypeT], typing.Generic[InputTypeT]):

    @abstractmethod
    def _create_log_event(
        self, data: dict[str, FieldValue], original: bytes | None = None
    ) -> LogEvent:
        pass

    async def test_get_next_returns_event(self):
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({}, original=b"")
        )
        event = await anext(self.object)
        assert isinstance(event, LogEvent)

    async def test_component_is_iterator(self):
        assert isinstance(self.object, AsyncIterator)

    async def test_component_is_input(self):
        assert isinstance(self.object, Input)

    @pytest.fixture(name="default_hmac_config")
    def _add_default_hmac_config(self):
        # TODO refactor to patch CONFIG instead
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )

    @pytest.mark.usefixtures("default_hmac_config")
    async def test_add_hmac_returns_true_if_hmac_options(self):
        assert self.object.preprocessor._add_hmac is True

    @pytest.mark.usefixtures("default_hmac_config")
    async def test_get_next_with_hmac_of_raw_message(self):
        return_value = {"message": "with_content"}
        raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(
                return_value.copy(), original=raw_encoded_test_event
            )
        )

        expected_event = self._create_log_event(
            data={
                "message": "with_content",
                "Hmac": {
                    "compressed_base64": "eJyrVspNLS5OTE9VslIqzyzJiE/OzytJzStRqgUAgKkJtg==",
                    "hmac": "dfe78753da634d7b76760488dbb2cf7bfe1b0e4e794930c36e98a984b6b6be63",
                },
            },
            original=raw_encoded_test_event,
        )
        connector_next_msg = await self.object.get_next(1)
        assert connector_next_msg == expected_event, "Output event with hmac is not as expected"

        decoded = base64.b64decode(connector_next_msg.data["Hmac"]["compressed_base64"])
        decoded_message = zlib.decompress(decoded)
        assert return_value == json.loads(
            decoded_message.decode("utf-8")
        ), "The hmac base massage was not correctly encoded and compressed. "

    async def test_get_next_with_hmac_of_subfield(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "hmac": {
                        "target": "message.with_subfield",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )

        return_value = {"message": {"with_subfield": "content"}}

        raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(
                return_value.copy(), original=raw_encoded_test_event
            )
        )
        expected_event = self._create_log_event(
            data={
                "message": {"with_subfield": "content"},
                "Hmac": {
                    "compressed_base64": "eJxLzs8rSc0rAQALywL8",
                    "hmac": "e01e02a09cb270eebf7ae846b96d7306681038bd279f85d44c77019e0c4f6316",
                },
            },
            original=raw_encoded_test_event,
        )

        connector_next_msg = await self.object.get_next(1)
        assert connector_next_msg == expected_event

        decoded = base64.b64decode(connector_next_msg.data["Hmac"]["compressed_base64"])
        decoded_message = zlib.decompress(decoded)
        assert return_value["message"]["with_subfield"] == decoded_message.decode(
            "utf-8"
        ), "The hmac base massage was not correctly encoded and compressed. "

    async def test_get_next_with_hmac_of_non_existing_subfield(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "hmac": {
                        "target": "non_existing_field",
                        "key": "hmac-test-key",
                        "output_field": "Hmac",
                    }
                }
            }
        )

        return_value = {"message": {"with_subfield": "content"}}

        raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(
                return_value.copy(), original=raw_encoded_test_event
            )
        )
        expected_error_message = "Couldn't find the hmac target field 'non_existing_field'"

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)

        assert error_event.data["event"] == json.dumps(return_value)
        assert expected_error_message in error_event.reason

    async def test_get_next_with_hmac_result_in_dotted_subfield(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "Hmac.dotted.subfield",
                    }
                }
            }
        )

        return_value = {"message": "with_content"}

        raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(
                return_value.copy(), original=raw_encoded_test_event
            )
        )
        expected_event = self._create_log_event(
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
            original=raw_encoded_test_event,
        )

        connector_next_msg = await self.object.get_next(1)
        assert connector_next_msg == expected_event
        decoded = base64.b64decode(
            connector_next_msg.data["Hmac"]["dotted"]["subfield"]["compressed_base64"]
        )
        decoded_message = zlib.decompress(decoded)
        assert return_value == json.loads(
            decoded_message.decode("utf-8")
        ), "The hmac base massage was not correctly encoded and compressed. "

    async def test_get_next_with_hmac_result_in_already_existing_subfield(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "hmac": {
                        "target": "<RAW_MSG>",
                        "key": "hmac-test-key",
                        "output_field": "message",
                    }
                }
            }
        )

        test_event = {"message": {"with_subfield": "content"}}

        raw_encoded_test_event = json.dumps(test_event, separators=(",", ":")).encode("utf-8")
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(test_event.copy(), original=raw_encoded_test_event)
        )

        expected_error_message = (
            "FieldExistsWarning: The following fields could not be written, because one or "
            "more subfields existed and could not be extended: message, event={'message': "
            "{'with_subfield': 'content'}}"
        )

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert expected_error_message in error_event.reason

    async def test_get_next_without_hmac(self):
        assert not self.CONFIG.get("preprocessing", {}).get("hmac")

        return_value = {"message": "with_content"}

        raw_encoded_test_event = json.dumps(return_value, separators=(",", ":")).encode("utf-8")
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(
                return_value.copy(), original=raw_encoded_test_event
            )
        )
        connector_next_msg = await self.object.get_next(1)
        assert connector_next_msg == self._create_log_event(
            data=return_value, original=raw_encoded_test_event
        )

    @mock.patch("logprep.ng.util.preprocessor.version", new=lambda _: "3.3.0")
    async def test_preprocessing_version_info_is_added_if_configured(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "version_info_target_field": "version_info",
                    "hmac": {"target": "", "key": "", "output_field": ""},
                },
            }
        )
        self.object.preprocessor.set_config_version_info("unset")

        return_value = {"any": "content"}

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(return_value, original=None)
        )
        result = await self.object.get_next(0.01)
        assert result.data.get("version_info", {}).get("logprep") == "3.3.0"
        assert result.data.get("version_info", {}).get("configuration") == "unset"

    async def test_pipeline_preprocessing_does_not_add_versions_if_target_field_exists_already(
        self,
    ):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "version_info_target_field": "version_info",
                    "hmac": {"target": "", "key": "", "output_field": ""},
                }
            }
        )

        test_event = {"any": "content", "version_info": "something random"}

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(test_event, original=b"123")
        )

        expected_error_message = (
            "FieldExistsWarning: The following fields could not be written, because one or "
            "more subfields existed and could not be extended: version_info, "
            "event={'any': 'content', 'version_info': 'something random'}"
        )

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert expected_error_message in error_event.reason

    async def test_pipeline_preprocessing_only_version_information(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "version_info_target_field": "version_info",
                }
            }
        )

        test_event = {"any": "content", "version_info": "something random"}

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(test_event, original=b"123")
        )

        expected_error_message = (
            "FieldExistsWarning: The following fields could not be written, because one or "
            "more subfields existed and could not be extended: version_info, "
            "event={'any': 'content', 'version_info': 'something random'}"
        )

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert expected_error_message in error_event.reason

    async def test_connector_counts_processed_events(self):
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"event:": "test_event"}, original=b"")
        )

        self.object.metrics.number_of_processed_events = 0

        await self.object.get_next(0.01)

        assert self.object.metrics.number_of_processed_events == 1

    async def test_connector_metrics_does_not_count_if_no_event_was_retrieved(self):
        self.object._get_event = mock.AsyncMock(return_value=None)

        self.object.metrics.number_of_processed_events = 0
        assert await self.object.get_next(0.01) is None
        assert self.object.metrics.number_of_processed_events == 0

    async def test_get_next_adds_timestamp_if_configured(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "log_arrival_time_target_field": "arrival_time",
                }
            }
        )

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"any": "content"}, original=b"")
        )
        result = await self.object.get_next(0.01)
        assert "arrival_time" in result.data
        assert isinstance(result.data["arrival_time"], str)
        assert (
            TimeParser.now() - TimeParser.from_string(result.data["arrival_time"])
        ).total_seconds() > 0

    async def test_pipeline_preprocessing_does_not_add_log_arrival_time_if_target_field_exists_already(
        self,
    ):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "log_arrival_time_target_field": "arrival_time",
                }
            }
        )

        test_event = {"any": "content", "arrival_time": "does not matter"}

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(test_event, original=b"123")
        )

        expected_error_message = (
            "FieldExistsWarning: The following fields could not be written, because one "
            "or more subfields existed and could not be extended: arrival_time, "
            "event={'any': 'content', 'arrival_time': 'does not matter'}"
        )

        error_event = await self.object.get_next(1)
        assert isinstance(error_event, ErrorEvent)
        assert expected_error_message in error_event.reason

    async def test_pipeline_preprocessing_add_log_arrival_time_if_target_parent_field_exists_already_and_is_dict(
        self,
    ):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "log_arrival_time_target_field": "event.created",
                }
            }
        )

        return_value = {"any": "content", "event": {"does not": "matter"}}

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(return_value, original=None)
        )
        event = await self.object.get_next(0.01)
        time_value = get_dotted_field_value(event.data, "event.created")
        assert time_value
        iso8601_regex = (
            r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|([+-]\d{2}:\d{2})$)"
        )
        assert re.search(iso8601_regex, time_value)

    async def test_pipeline_preprocessing_add_log_arrival_time_if_target_parent_field_exists_already_and_not_dict(
        self,
    ):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "log_arrival_time_target_field": "event.created",
                }
            }
        )
        return_value = {"any": "content", "event": "does not matter"}

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(return_value, original=None)
        )
        event = await self.object.get_next(0.01)
        time_value = get_dotted_field_value(event.data, "event.created")
        assert time_value
        iso8601_regex = (
            r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|([+-]\d{2}:\d{2})$)"
        )
        assert re.search(iso8601_regex, time_value)
        original_event = get_dotted_field_value(event.data, "event.@original")
        assert original_event == "does not matter"

    async def test_pipeline_preprocessing_adds_timestamp_delta_if_configured(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "log_arrival_time_target_field": "arrival_time",
                    "log_arrival_timedelta": {
                        "target_field": "log_arrival_timedelta",
                        "reference_field": "@timestamp",
                    },
                }
            }
        )

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(
                {"any": "content", "@timestamp": "1999-09-09T09:09:09.448319+02:00"}, b""
            )
        )

        result = await self.object.get_next(0.01)
        assert "log_arrival_timedelta" in result.data
        assert isinstance(result.data["log_arrival_timedelta"], float)

    async def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_configured_but_reference_field_not_found(
        self,
    ):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "log_arrival_time_target_field": "arrival_time",
                    "log_arrival_timedelta": {
                        "target_field": "log_arrival_timedelta",
                        "reference_field": "@timestamp",
                    },
                }
            }
        )

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"any": "content"}, b"")
        )

        result = await self.object.get_next(0.01)
        assert "arrival_time" in result.data
        assert "log_arrival_timedelta" not in result.data

    async def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_not_configured(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "log_arrival_time_target_field": "arrival_time",
                }
            }
        )

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"any": "content"}, b'{"any":"content"}')
        )
        result = await self.object.get_next(0.01)
        assert "arrival_time" in result.data

    async def test_add_full_event_to_target_field_with_string_format(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "add_full_event_to_target_field": {
                        "format": "str",
                        "target_field": "event.original",
                    },
                }
            }
        )

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"any": "content"}, b'{"any":"content"}')
        )

        result = await self.object.get_next(0.01)
        expected = {"event": {"original": '"{\\"any\\":\\"content\\"}"'}}
        assert result.data == expected, f"{expected} is not the same as {result.data}"

    async def test_add_full_event_to_targetfield_with_same_name(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "add_full_event_to_target_field": {
                        "format": "str",
                        "target_field": "any.content",
                    },
                }
            }
        )

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"any": "content"}, b'{"any":"content"}')
        )

        result = await self.object.get_next(0.01)
        expected = {"any": {"content": '"{\\"any\\":\\"content\\"}"'}}
        assert result.data == expected, f"{expected} is not the same as {result.data}"

    @mock.patch("logprep.ng.util.preprocessor.version", new=lambda _: "3.3.0")
    async def test_add_full_event_to_targetfield_vs_version_info_target(self):
        self.object = self._create_test_instance(
            config_patch={
                "preprocessing": {
                    "add_full_event_to_target_field": {
                        "format": "str",
                        "target_field": "any.content",
                    },
                    "version_info_target_field": "version_info",
                }
            }
        )
        self.object.preprocessor.set_config_version_info("unset")

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"any": "content"}, b'{"any":"content"}')
        )

        result = await self.object.get_next(0.01)
        expected = {
            "any": {"content": '"{\\"any\\":\\"content\\"}"'},
            "version_info": {"logprep": "3.3.0", "configuration": "unset"},
        }
        assert result.data == expected, f"{expected} is not the same as {result.data}"

    async def test_add_full_event_to_target_field_with_dict_format(self):
        preprocessing_config = {
            "preprocessing": {
                "add_full_event_to_target_field": {
                    "format": "dict",
                    "target_field": "event.original",
                },
            }
        }
        self.object = self._create_test_instance(config_patch=preprocessing_config)

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"any": "content"}, b'{"any": "content"}')
        )

        result = await self.object.get_next(0.01)
        expected = {"event": {"original": {"any": "content"}}}
        assert result.data == expected, f"{expected} is not the same as {result.data}"

    async def test_pipeline_preprocessing_does_not_add_timestamp_delta_if_configured_but_log_arrival_timestamp_not(
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
        self.object = self._create_test_instance(config_patch=preprocessing_config)

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"any": "content"}, b"")
        )

        result = await self.object.get_next(0.01)
        assert result.data == {"any": "content"}

    async def test_preprocessing_enriches_by_multiple_env_variables(self):
        preprocessing_config = {
            "preprocessing": {
                "enrich_by_env_variables": {
                    "enriched_field1": "TEST_ENV_VARIABLE_FOO",
                    "enriched_field2": "TEST_ENV_VARIABLE_BAR",
                },
            }
        }
        self.object = self._create_test_instance(config_patch=preprocessing_config)

        os.environ["TEST_ENV_VARIABLE_FOO"] = "test_value_foo"
        os.environ["TEST_ENV_VARIABLE_BAR"] = "test_value_bar"
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"any": "content"}, b'{"any":"content"}')
        )
        result = await self.object.get_next(0.01)
        assert result.data == {
            "any": "content",
            "enriched_field1": "test_value_foo",
            "enriched_field2": "test_value_bar",
        }

    async def test_get_next_counts_number_of_processed_events(self):
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(
                {"message": "test message"}, b'{"message":"test message"}'
            )
        )
        self.object.metrics.number_of_processed_events = 0
        await self.object.get_next(0.01)

        assert self.object.metrics.number_of_processed_events == 1

    async def test_get_next_does_not_count_number_of_processed_events_if_event_is_none(self):
        self.object.metrics.number_of_processed_events = 0
        self.object._get_event = mock.AsyncMock(return_value=None)
        await self.object.get_next(0.01)
        assert self.object.metrics.number_of_processed_events == 0

    async def test_get_next_has_time_measurement(self):
        mock_metric = mock.MagicMock()
        self.object.metrics.processing_time_per_event = mock_metric
        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event(
                {"message": "test message"}, b'{"message": "test message"}'
            )
        )
        await self.object.get_next(0.01)
        assert isinstance(self.object.metrics.processing_time_per_event, mock.MagicMock)
        # asserts entering context manager in metrics.metrics.Metric.measure_time
        mock_metric.assert_has_calls([mock.call.tracker.labels().time().__enter__()])

    async def test_input_iterator(self):
        batch_events = [
            {"valid": "json_1"},
            {"valid": "json_2"},
            {"valid": "json_3"},
        ]

        def get_next_mock(*args, **kwargs):
            if batch_events:
                return batch_events.pop(0)
            return None

        self.object.get_next = mock.AsyncMock(side_effect=get_next_mock)

        assert await anext(self.object) == {"valid": "json_1"}
        assert await anext(self.object) == {"valid": "json_2"}
        assert await anext(self.object) == {"valid": "json_3"}
        assert await anext(self.object) is None

    async def test_add_full_event_to_target_field_without_clear(self):
        preprocessing_config = {
            "preprocessing": {
                "add_full_event_to_target_field": {
                    "format": "str",
                    "target_field": "event.original",
                    "clear_event": False,
                },
            }
        }
        self.object = self._create_test_instance(config_patch=preprocessing_config)

        self.object._get_event = mock.AsyncMock(
            return_value=self._create_log_event({"any": "content"}, b'{"any":"content"}')
        )
        result = await self.object.get_next(0.01)
        expected = {"any": "content", "event": {"original": '"{\\"any\\":\\"content\\"}"'}}
        assert result.data == expected, f"{expected} is not the same as {result.data}"


def _create_log_event(data: dict[str, FieldValue], output_target: str | None = None) -> OutputEvent:
    return LogEvent(data, output_target=output_target, original=b"", input_meta=InputMeta())


class BaseOutputTestCase(BaseConnectorTestCase[OutputTypeT], typing.Generic[OutputTypeT]):

    @staticmethod
    def _create_log_event(
        data: dict[str, FieldValue], output_target: str | None = None
    ) -> OutputEvent:
        return LogEvent(data, output_target=output_target, original=b"", input_meta=InputMeta())

    async def test_is_output_instance(self):
        assert isinstance(self.object, Output)

    @pytest.fixture
    @abstractmethod
    def mock_output_delivery_for_events(
        self,
    ) -> Callable[[Sequence[bool | Exception]], None]:
        """
        Returns a helper method which configures the mock in the concrete test class.
        Whereas `True` indicates a successful store operation, `False` represents a failed
        operation which has been gracefully handled by the used client.
        `Exception` on the other hand is an error scenario which the client was not able
        (or does not indent to) to handle gracefully.
        """

    @pytest.mark.parametrize(("count"), [pytest.param(n, id=f"{n} events") for n in [0, 1, 2, 5]])
    async def test_store_counts_processed_events(self, count, mock_output_delivery_for_events):
        await self.object.setup()
        self.object.metrics.number_of_processed_events = 0

        events = [self._create_log_event({"message": f"test {i}"}) for i in range(count)]
        mock_output_delivery_for_events([True for _ in events])
        await self.object.store(events)

        assert self.object.metrics.number_of_processed_events == count

    @pytest.mark.parametrize(("count"), [pytest.param(n, id=f"{n} events") for n in [0, 1, 2, 5]])
    async def test_store_counts_error_events(self, count, mock_output_delivery_for_events):
        await self.object.setup()
        self.object.metrics.number_of_errors = 0

        events = [self._create_log_event({"message": f"test {i}"}) for i in range(count)]
        mock_output_delivery_for_events([False for _ in events])
        await self.object.store(events)

        assert self.object.metrics.number_of_errors == count

    @pytest.mark.parametrize(("count"), [pytest.param(n, id=f"{n} events") for n in [0, 1, 2, 5]])
    async def test_store_counts_error_events_for_client_failures(
        self, count, mock_output_delivery_for_events
    ):
        await self.object.setup()
        self.object.metrics.number_of_errors = 0

        events = [self._create_log_event({"message": f"test {i}"}) for i in range(count)]
        mock_output_delivery_for_events([Exception("unexpected client failure") for _ in events])
        await self.object.store(events)

        assert self.object.metrics.number_of_errors == count

    async def test_store_handles_uncaught_exception(self):
        await self.object.setup()
        self.object.metrics.number_of_errors = 0

        event_with_target = self._create_log_event({"message": "test 1"}, output_target="something")
        event_without_target = self._create_log_event({"message": "test 1"}, output_target=None)
        failure_reason = Exception("test error")

        with mock.patch.object(self.object, "_store") as mock_write:
            mock_write.side_effect = failure_reason
            await self.object.store([event_with_target, event_without_target])

        assert self.object.metrics.number_of_errors == 2
        assert event_with_target.errors == [failure_reason]
        assert event_without_target.errors == [failure_reason]
