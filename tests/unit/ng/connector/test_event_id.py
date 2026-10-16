# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
import re
from copy import deepcopy
from unittest import mock
from uuid import UUID

import pytest

from logprep.abc.input import CriticalInputError
from logprep.factory import Factory
from logprep.ng.abc.event import ErrorEvent, InputMeta, LogEvent
from logprep.ng.util.preprocessor import PreprocessingError
from tests.unit.connector.test_event_id import (
    GENERATED_ID,
)
from tests.unit.connector.test_event_id import (
    error_test_cases as non_ng_error_test_cases,
)
from tests.unit.connector.test_event_id import (
    example_test_cases as non_ng_example_test_cases,
)
from tests.unit.connector.test_event_id import shared_test_cases as non_ng_test_cases

example_test_cases = deepcopy(non_ng_example_test_cases)
test_cases = deepcopy(non_ng_test_cases)
error_test_cases = deepcopy(non_ng_error_test_cases)


class TestEventId:
    @pytest.mark.parametrize("configuration, event, expected, _context", test_cases)
    async def test_generates_and_stores_event_ids(self, configuration, event, expected, _context):
        input_connector = Factory.create(
            {"input": {**deepcopy(configuration["input"]), "documents": []}}
        )
        output = Factory.create({"output": deepcopy(configuration["output"])})
        raw_events = [
            LogEvent(deepcopy(event), original=None, input_meta=InputMeta()) for _ in range(2)
        ]
        with mock.patch.object(input_connector, "_get_event", side_effect=raw_events):
            events = [await input_connector.get_next(0.01) for _ in range(2)]

        assert all(isinstance(item, LogEvent) for item in events)
        assert all(not item.is_failed() for item in events)
        assert all("@LOGPREP_EVENT_ID" not in item.data for item in events)
        if set(configuration["input"]["preprocessing"]) <= {"source_id"}:
            assert [item.data for item in events] == [event, event]

        event_ids = [item.event_id for item in events]
        if expected["event_id"] == GENERATED_ID:
            assert len(set(event_ids)) == 2
            for event_id in event_ids:
                assert UUID(event_id).version == 4
                assert UUID(event_id).hex == event_id
        else:
            assert event_ids == [expected["event_id"]] * 2

        await output.store(events)

        assert len(output.events) == 2
        for index, stored in enumerate(output.events):
            expected_document = deepcopy(expected["data"])
            if expected["event_id"] == GENERATED_ID:
                expected_document = json.loads(
                    json.dumps(expected_document).replace(GENERATED_ID, event_ids[index])
                )
            assert stored.data == expected_document
            assert stored.event_id == event_ids[index]
            assert stored.stored
            assert not stored.is_failed()

    @pytest.mark.parametrize("configuration, event, error, message", error_test_cases)
    async def test_rejects_invalid_event_ids(self, configuration, event, error, message):
        if error is not CriticalInputError:
            with pytest.raises(error, match=message):
                input_connector = Factory.create(
                    {"input": {**deepcopy(configuration["input"]), "documents": []}}
                )
                Factory.create({"output": deepcopy(configuration["output"])})
            return

        input_connector = Factory.create(
            {"input": {**deepcopy(configuration["input"]), "documents": []}}
        )
        raw_event = LogEvent(deepcopy(event), original=None, input_meta=InputMeta())
        with mock.patch.object(input_connector, "_get_event", return_value=raw_event):
            result = await input_connector.get_next(0.01)

        assert isinstance(result, ErrorEvent)
        assert len(raw_event.errors) == 1
        assert isinstance(raw_event.errors[0], PreprocessingError)
        assert re.search(message, str(raw_event.errors[0]))
        assert json.loads(result.data["event"]) == event
