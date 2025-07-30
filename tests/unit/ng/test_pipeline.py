# pylint: disable=missing-docstring
from unittest import mock

import pytest

from logprep.factory import Factory
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.pipeline import Pipeline


@pytest.fixture(name="input_connector")
def get_input_mock():
    return iter(
        [
            LogEvent({"message": "Log message 1"}, original=b"", state=EventStateType.RECEIVED),
            LogEvent({"message": "Log message 2"}, original=b"", state=EventStateType.RECEIVED),
        ]
    )


@pytest.fixture(name="processors")
def get_processors_mock():

    return [
        Factory.create(
            {
                "processor": {
                    "type": "ng_generic_adder",
                    "rules": [
                        {
                            "filter": "*",
                            "generic_adder": {"add": {"event.tags": "generic added tag"}},
                        }
                    ],
                }
            }
        ),
    ]


class TestPipeline:
    def test_init(self, input_connector, processors):
        pipeline = Pipeline(input_connector, processors)
        assert isinstance(pipeline, Pipeline)

    def test_process_event(self, input_connector, processors):
        pipeline = Pipeline(input_connector, processors)
        event = next(input_connector)
        processed_event = pipeline.process_event(event)

        assert isinstance(processed_event, LogEvent)
        assert "generic added tag" in processed_event.get_dotted_field_value("event.tags")

    def test_process_pipeline_success(self, input_connector, processors):
        pipeline = Pipeline(input_connector, processors)
        processed_events = list(pipeline.process_pipeline())

        assert len(processed_events) == 2
        for event in processed_events:
            assert isinstance(event, LogEvent)
            assert "generic added tag" in event.get_dotted_field_value("event.tags")
            assert event.state.current_state == EventStateType.PROCESSED

    def test_process_pipeline_failure(self, input_connector, processors):
        with mock.patch.object(
            processors[0], "_apply_rules", side_effect=[None, Exception("Processing error")]
        ):
            pipeline = Pipeline(input_connector, processors)
            processed_events = list(pipeline.process_pipeline())

        assert len(processed_events) == 2
        assert len(processed_events[0].errors) == 0
        assert len(processed_events[1].errors) == 1
        assert processed_events[0].state.current_state == EventStateType.PROCESSED
        assert processed_events[1].state.current_state == EventStateType.FAILED
