# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=line-too-long

from typing import Iterator
from unittest import mock

import pytest

from logprep.factory import Factory
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.pseudonym_event import PseudonymEvent
from logprep.ng.pipeline import Pipeline


@pytest.fixture(name="input_connector")
def get_input_mock():
    return iter(
        [
            LogEvent({"message": "Log message 1"}, original=b"", state=EventStateType.RECEIVED),
            LogEvent({"message": "Log message 2"}, original=b"", state=EventStateType.RECEIVED),
            LogEvent({"user": {"name": "John Doe"}}, original=b"", state=EventStateType.RECEIVED),
        ]
    )


@pytest.fixture(name="processors", scope="session")
def get_processors_mock():
    processors = [
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
        Factory.create(
            {
                "pseudo_this": {
                    "type": "ng_pseudonymizer",
                    "pubkey_analyst": "examples/exampledata/rules/pseudonymizer/example_analyst_pub.pem",
                    "pubkey_depseudo": "examples/exampledata/rules/pseudonymizer/example_depseudo_pub.pem",
                    "regex_mapping": "examples/exampledata/rules/pseudonymizer/regex_mapping.yml",
                    "hash_salt": "a_secret_tasty_ingredient",
                    "outputs": [{"opensearch": "pseudonyms"}],
                    "rules": [
                        {
                            "filter": "user.name",
                            "pseudonymizer": {
                                "id": "pseudonymizer-1a3c69b2-5d54-4b6b-ab07-c7ddbea7917c",
                                "mapping": {"user.name": "RE_WHOLE_FIELD"},
                            },
                        }
                    ],
                    "max_cached_pseudonyms": 1000000,
                }
            }
        ),
    ]
    for processor in processors:
        processor.setup()
    return processors


class TestPipeline:
    def test_init(self, input_connector, processors):
        pipeline = Pipeline(input_connector, processors)
        assert isinstance(pipeline, Pipeline)
        assert isinstance(pipeline, Iterator)

    def test_pipeline_next_raises_not_implemented_error(self, input_connector, processors):
        pipeline = Pipeline(input_connector, processors)

        with pytest.raises(NotImplementedError):
            next(pipeline)

    def test_process_pipeline_success(self, input_connector, processors):
        processed_events = list(Pipeline(input_connector, processors))

        for event in processed_events:
            assert isinstance(event, LogEvent)
            assert not event.errors
            assert "generic added tag" in event.get_dotted_field_value("event.tags")
            assert event.state.current_state == EventStateType.PROCESSED

    def test_process_pipeline_failure(self, input_connector, processors):
        with mock.patch.object(
            processors[0], "_apply_rules", side_effect=[None, Exception("Processing error")]
        ):
            pipeline = Pipeline(input_connector, processors)
            processed_events = list(pipeline)

        assert len(processed_events[0].errors) == 0
        assert len(processed_events[1].errors) == 1
        assert processed_events[0].state.current_state == EventStateType.PROCESSED
        assert processed_events[1].state.current_state == EventStateType.FAILED

    def test_process_pipeline_generates_extra_data(self, input_connector, processors):
        pipeline = Pipeline(input_connector, processors)
        processed_events = list(pipeline)

        for event in processed_events:
            assert isinstance(event, LogEvent)
            assert not event.errors
        assert len(processed_events[2].extra_data) == 1
        extra_data_event = processed_events[2].extra_data[0]
        assert isinstance(extra_data_event, PseudonymEvent)
        assert extra_data_event.state.current_state == EventStateType.PROCESSED

    def test_process_pipeline_none_input(self, processors):
        empty_input = iter([None, None, None])
        pipeline = Pipeline(empty_input, processors)
        processed_events = list(pipeline)
        assert processed_events == [None, None, None]

    def test_process_pipeline_empty_input(self, processors):
        empty_input = iter([])
        pipeline = Pipeline(empty_input, processors)
        processed_events = list(pipeline)
        assert not processed_events

    def test_process_pipeline_empty_events_in_input(self, processors):
        empty_input = iter([LogEvent({}, original=b"") for _ in range(5)])
        pipeline = Pipeline(empty_input, processors)
        processed_events = list(pipeline)
        assert processed_events == [None for _ in range(5)]

    def test_empty_documents_are_not_forwarded_to_other_processors(
        self, input_connector, processors
    ):
        with mock.patch.object(
            processors[0], "process", side_effect=lambda event: event.data.clear()
        ):
            with mock.patch.object(processors[1], "process"):
                pipeline = Pipeline(input_connector, processors)
                processed_events = list(pipeline)
                assert len(processed_events) == 3
                assert processed_events[0].data == {}
                assert processors[0].process.call_count == 3
                assert processors[1].process.call_count == 0

    def test_setup_calls_processor_setups(self, input_connector):
        processors = [mock.MagicMock() for _ in range(5)]
        pipeline = Pipeline(input_connector, processors)
        pipeline.setup()
        for processor in processors:
            processor.setup.assert_called_once()

    def test_shut_down_calls_processor_shut_down(self, input_connector):
        processors = [mock.MagicMock() for _ in range(5)]
        pipeline = Pipeline(input_connector, processors)
        pipeline.shut_down()
        for processor in processors:
            processor.shut_down.assert_called_once()
