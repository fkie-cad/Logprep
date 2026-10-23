# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
from copy import deepcopy
from uuid import UUID

import pytest

from logprep.abc.input import CriticalInputError
from logprep.factory import Factory
from logprep.framework.pipeline import Pipeline
from logprep.util.configuration import Configuration
from logprep.util.helper import FieldValue
from tests.conftest import normalize_test_cases

GENERATED_ID = "<generated UUID>"


def config(source_id=None, *, preprocessing=None, target_field=None):
    input_preprocessing = deepcopy(preprocessing or {})
    if source_id is not None:
        input_preprocessing["source_id"] = source_id
    output = {"type": "dummy_output"}
    if target_field is not None:
        output["target_id_field"] = target_field
    return {
        "input": {"type": "dummy_input", "preprocessing": input_preprocessing},
        "output": output,
    }


example_test_cases = [
    pytest.param(
        config(),
        {"message": "hello"},
        {"event_id": None, "data": {"message": "hello"}},
        id="leaves events unchanged by default",
    ),
    pytest.param(
        config({"on_missing": "GENERATE"}),
        {"message": "hello"},
        {
            "event_id": GENERATED_ID,
            "data": {"message": "hello", "@metadata": {"event": {"id": GENERATED_ID}}},
        },
        id="generates a unique UUID for each event when enabled",
    ),
    pytest.param(
        config({"source_field": "request.id"}, target_field="trace.id"),
        {"message": "hello", "request": {"id": "request-123"}},
        {
            "event_id": "request-123",
            "data": {
                "message": "hello",
                "request": {"id": "request-123"},
                "trace": {"id": "request-123"},
            },
        },
        id="copies a dotted source ID to the configured output field",
    ),
    pytest.param(
        config({"source_field": "request.id"}),
        {"message": "hello"},
        {"event_id": None, "data": {"message": "hello"}},
        id="ignores a missing source ID by default",
    ),
]


missing_source_events: list[tuple[str, dict[str, FieldValue]]] = [
    ("the dotted source field is absent", {"message": "hello"}),
    ("the source parent is a scalar", {"request": "scalar"}),
    ("the source parent is null", {"request": None}),
    ("the source parent is an empty dictionary", {"request": {}}),
]

shared_test_cases = normalize_test_cases(
    *example_test_cases,
    pytest.param(
        config({}),
        {},
        {"event_id": None, "data": {}},
        id="ignores an empty event with an empty source configuration",
    ),
    *[
        pytest.param(
            config({"source_field": "request.id", "on_missing": "GENERATE"}),
            event,
            {
                "event_id": GENERATED_ID,
                "data": {**event, "@metadata": {"event": {"id": GENERATED_ID}}},
            },
            id=f"generates an ID when {description}",
        )
        for description, event in missing_source_events
    ],
    *[
        pytest.param(
            config({"source_field": "request.id"}),
            event,
            {"event_id": None, "data": event},
            id=f"ignores a missing ID by default when {description}",
        )
        for description, event in missing_source_events
    ],
    pytest.param(
        config(),
        {"message": "hello", "@metadata": {"event": {"id": "existing"}}},
        {
            "event_id": None,
            "data": {"message": "hello", "@metadata": {"event": {"id": "existing"}}},
        },
        id="leaves existing output metadata unchanged when ID generation is disabled",
    ),
    *[
        pytest.param(
            config({"source_field": "id", "on_missing": policy}),
            {"id": "upstream-id"},
            {
                "event_id": "upstream-id",
                "data": {"id": "upstream-id", "@metadata": {"event": {"id": "upstream-id"}}},
            },
            id=f"preserves a supplied ID with the {policy} missing-source policy",
        )
        for policy in ("GENERATE", "FAIL", "IGNORE")
    ],
    pytest.param(
        config({"source_field": r"event\.id"}),
        {"event.id": "literal-id"},
        {
            "event_id": "literal-id",
            "data": {"event.id": "literal-id", "@metadata": {"event": {"id": "literal-id"}}},
        },
        id="reads a source key containing an escaped dot",
    ),
    pytest.param(
        config({"source_field": "items.0.id"}),
        {"items": [{"id": "first-id"}, {"id": "second-id"}]},
        {
            "event_id": "first-id",
            "data": {
                "items": [{"id": "first-id"}, {"id": "second-id"}],
                "@metadata": {"event": {"id": "first-id"}},
            },
        },
        id="reads a source ID from an indexed list item",
    ),
    pytest.param(
        config({"source_field": "id"}, target_field="event_id"),
        {"id": "0"},
        {"event_id": "0", "data": {"id": "0", "event_id": "0"}},
        id="accepts a nonempty string containing zero and writes a top-level target",
    ),
    pytest.param(
        config({"source_field": "id"}, target_field=r"event\.id"),
        {"id": "identifier-ä"},
        {"event_id": "identifier-ä", "data": {"id": "identifier-ä", "event.id": "identifier-ä"}},
        id="preserves Unicode IDs and writes a target key containing an escaped dot",
    ),
    *[
        pytest.param(
            config({"source_field": "id"}),
            {"id": "upstream-id", "@metadata": parent},
            {
                "event_id": "upstream-id",
                "data": {"id": "upstream-id", "@metadata": {"event": {"id": "upstream-id"}}},
            },
            id=f"overwrites a {description} output parent",
        )
        for description, parent in [
            ("scalar", "old"),
            ("list", ["old"]),
            ("null", None),
        ]
    ],
    pytest.param(
        config({"source_field": "id"}),
        {"id": "upstream-id", "@metadata": {"event": {"id": "old", "keep": True}, "keep": 0}},
        {
            "event_id": "upstream-id",
            "data": {
                "id": "upstream-id",
                "@metadata": {"event": {"id": "upstream-id", "keep": True}, "keep": 0},
            },
        },
        id="overwrites an existing ID while preserving sibling metadata",
    ),
    pytest.param(
        config({"source_field": "id"}, target_field="id"),
        {"id": "upstream-id"},
        {"event_id": "upstream-id", "data": {"id": "upstream-id"}},
        id="allows the output target to be the source field",
    ),
    pytest.param(
        config(
            {"source_field": "request.id", "on_missing": "FAIL"},
            preprocessing={
                "add_full_event_to_target_field": {
                    "format": "dict",
                    "target_field": "event.original",
                    "clear_event": True,
                }
            },
        ),
        {"request": {"id": "upstream-id"}, "message": "hello"},
        {
            "event_id": "upstream-id",
            "data": {
                "event": {"original": {"request": {"id": "upstream-id"}, "message": "hello"}},
                "@metadata": {"event": {"id": "upstream-id"}},
            },
        },
        id="captures the source ID before full-event preprocessing clears the event",
    ),
    pytest.param(
        config(
            {"on_missing": "GENERATE"},
            preprocessing={
                "add_full_event_to_target_field": {
                    "format": "dict",
                    "target_field": "event.original",
                    "clear_event": False,
                }
            },
        ),
        {"message": "hello"},
        {
            "event_id": GENERATED_ID,
            "data": {
                "message": "hello",
                "event": {"original": {"message": "hello"}},
                "@metadata": {"event": {"id": GENERATED_ID}},
            },
        },
        id="keeps the generated ID out of the captured original event",
    ),
    pytest.param(
        config(
            {"on_missing": "GENERATE"},
            preprocessing={
                "hmac": {"target": "<RAW_MSG>", "key": "hmac-test-key", "output_field": "Hmac"}
            },
        ),
        {"message": "test message"},
        {
            "event_id": GENERATED_ID,
            "data": {
                "message": "test message",
                "Hmac": {
                    "hmac": "8b2d75efcba66476e5551d44065128bacff2f090db5b08d7a0201c33e3f651f5",
                    "compressed_base64": "eJyrVspNLS5OTE9VslIqSS0uUYBxawF+Fwll",
                },
                "@metadata": {"event": {"id": GENERATED_ID}},
            },
        },
        id="keeps HMACs stable for identical raw-less events with different generated IDs",
    ),
)


test_cases = normalize_test_cases(
    *shared_test_cases,
    pytest.param(
        {
            **config({"source_field": "id"}, target_field="meta.event_id"),
            "additional_outputs": {
                "second": {"type": "dummy_output", "target_id_field": "meta.event_id"},
                "disabled": {
                    "type": "dummy_output",
                    "default": False,
                    "target_id_field": "meta.event_id",
                },
            },
        },
        {
            "id": "upstream-id",
            "meta": {"event_id": "old-id", "keep": 0},
        },
        {
            "event_id": "upstream-id",
            "data": {
                "id": "upstream-id",
                "meta": {"event_id": "upstream-id", "keep": 0},
            },
            "additional_data": {
                "second": {
                    "id": "upstream-id",
                    "meta": {"event_id": "upstream-id", "keep": 0},
                },
                "disabled": None,
            },
        },
        id="stores a shared dotted ID target across outputs",
    ),
)


error_test_cases = [
    pytest.param(
        config({"source_field": "request.id", "on_missing": "FAIL"}),
        {"message": "hello"},
        CriticalInputError,
        r"source field request\.id is missing",
        id="fails when a required source ID is missing",
    ),
    pytest.param(
        config({"on_missing": "FAIL"}),
        {"message": "hello"},
        CriticalInputError,
        "source field None is missing",
        id="fails when no source field is configured and generation is forbidden",
    ),
    *[
        pytest.param(
            config({"source_field": "id", "on_missing": policy}),
            {"id": value},
            CriticalInputError,
            "must contain a string",
            id=f"rejects {description} source IDs with the {policy} policy",
        )
        for policy in ("GENERATE", "FAIL", "IGNORE")
        for description, value in [
            ("empty", ""),
            ("null", None),
            ("zero", 0),
            ("boolean", False),
            ("empty list", []),
            ("list", ["id"]),
            ("empty dictionary", {}),
            ("dictionary", {"id": "value"}),
        ]
    ],
    *[
        pytest.param(
            config({"on_missing": value}),
            {"message": "hello"},
            ValueError,
            "on_missing",
            id=f"rejects the invalid missing-source policy {value!r}",
        )
        for value in ("generate", "UNKNOWN", None)
    ],
    pytest.param(
        config({"source_field": ""}),
        {"message": "hello"},
        ValueError,
        "source_field",
        id="rejects an empty configured source path",
    ),
    *[
        pytest.param(
            config({"source_field": value}),
            {"message": "hello"},
            TypeError,
            "source_field",
            id=f"rejects a non-string configured source path {value!r}",
        )
        for value in (0, False, ["id"])
    ],
    *[
        pytest.param(
            {**config(), "output": {"type": "dummy_output", "target_id_field": value}},
            {"message": "hello"},
            TypeError,
            "target_id_field",
            id=f"rejects a non-string output target {value!r}",
        )
        for value in (0, None, ["id"])
    ],
]


class TestEventId:
    @pytest.mark.parametrize("configuration, event, expected, _context", test_cases)
    def test_generates_and_stores_event_ids(self, configuration, event, expected, _context):
        input_connector = Factory.create(
            {
                "input": {
                    **deepcopy(configuration["input"]),
                    "documents": [deepcopy(event) for _ in range(2)],
                }
            }
        )
        output_configs = {
            "output": deepcopy(configuration["output"]),
            **deepcopy(configuration.get("additional_outputs", {})),
        }
        pipeline = Pipeline(config=Configuration(output=output_configs, pipeline=[]))

        events = [input_connector.get_next(0.01) for _ in range(2)]
        event_ids = [item.get("@LOGPREP_EVENT_ID") for item in events]
        if expected["event_id"] == GENERATED_ID:
            assert len(set(event_ids)) == 2
            for event_id in event_ids:
                assert UUID(event_id).version == 4
                assert UUID(event_id).hex == event_id
        else:
            assert event_ids == [expected["event_id"]] * 2

        for item in events:
            pipeline._store_event(item)

        for name, output in pipeline._output.items():
            expected_data = (
                expected["data"] if name == "output" else expected["additional_data"][name]
            )
            if expected_data is None:
                assert output.events == []
                continue
            for index, stored in enumerate(output.events):
                expected_document = deepcopy(expected_data)
                if expected["event_id"] == GENERATED_ID:
                    expected_document = json.loads(
                        json.dumps(expected_document).replace(GENERATED_ID, event_ids[index])
                    )
                assert stored == expected_document
                assert "@LOGPREP_EVENT_ID" not in stored
            assert len(output.events) == 2

    @pytest.mark.parametrize("configuration, event, error, message", error_test_cases)
    def test_rejects_invalid_event_ids(self, configuration, event, error, message):
        with pytest.raises(error, match=message) as raised:
            input_connector = Factory.create(
                {"input": {**deepcopy(configuration["input"]), "documents": [event]}}
            )
            Factory.create({"output": deepcopy(configuration["output"])})
            input_connector.get_next(0.01)

        if error is CriticalInputError:
            assert raised.value.raw_input == event
