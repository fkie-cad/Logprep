# pylint: disable=missing-docstring
# pylint: disable=protected-access
from unittest import mock

import pytest

from logprep.factory import Factory
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.pipeline import Pipeline
from logprep.ng.sender import Sender


@pytest.fixture(name="input_connector")
def get_input_mock():
    return iter(
        [
            LogEvent({"message": "Log message 1"}, original=b"", state=EventStateType.RECEIVED),
            LogEvent({"message": "Log message 2"}, original=b"", state=EventStateType.RECEIVED),
            LogEvent({"user": {"name": "John Doe"}}, original=b"", state=EventStateType.RECEIVED),
        ]
    )


@pytest.fixture(name="processors")
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
                    "outputs": [{"kafka": "pseudonyms"}],
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


@pytest.fixture(name="opensearch_output")
def get_opensearch_mock():
    return Factory.create(
        {
            "opensearch": {
                "type": "ng_dummy_output",
            }
        }
    )


@pytest.fixture(name="kafka_output")
def get_kafka_mock():
    return Factory.create(
        {
            "kafka": {
                "type": "ng_dummy_output",
                "default": False,
            }
        }
    )


@pytest.fixture(name="error_output")
def get_error_output_mock():
    return Factory.create(
        {
            "error": {
                "type": "ng_dummy_output",
            }
        }
    )


@pytest.fixture(name="pipeline")
def get_pipeline_mock(input_connector, processors):
    """Create a mock for the Pipeline class."""
    return Pipeline(input_connector, processors)


class TestSender:
    """Test the Sender class."""

    def test_sender_initialization(self, pipeline, opensearch_output):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=None)
        assert sender
        assert sender._pipeline == pipeline
        assert sender._outputs == {opensearch_output.name: opensearch_output}
        assert sender._error_output is None

    def test_sender_sends_events_to_output(self, pipeline, opensearch_output, kafka_output):
        sender = Sender(
            pipeline=pipeline, outputs=[opensearch_output, kafka_output], error_output=None
        )
        events = list(sender)
        assert len(events) == 3
        assert len(opensearch_output.events) == 3, "3 log events "
        assert len(kafka_output.events) == 1, "1 extra data event"

    def test_sender_sends_failed_events_to_error_output(
        self, pipeline, opensearch_output, error_output, kafka_output
    ):
        sender = Sender(
            pipeline=pipeline, outputs=[opensearch_output, kafka_output], error_output=error_output
        )
        with mock.patch.object(sender._pipeline._processors[0], "_apply_rules") as mock_process:
            mock_process.side_effect = Exception("Processing error")
            events = list(sender)
            assert len(events) == 3
            assert len(opensearch_output.events) == 0, "no events delivered"
            assert len(kafka_output.events) == 1, "1 extra data event"
            assert len(error_output.events) == 3, "3 failed events sent to error output"

    def test_sender_sends_processed_events_to_all_default_outputs(
        self, pipeline, opensearch_output, kafka_output
    ):
        sender = Sender(
            pipeline=pipeline,
            outputs=[opensearch_output, kafka_output],
            error_output=None,
        )
        events = list(sender)
        assert len(events) == 3
        assert len(opensearch_output.events) == 3
        assert len(kafka_output.events) == 3

    def test_sender_sends_extra_data(self, pipeline, opensearch_output):
        sender = Sender(pipeline=pipeline, outputs=[opensearch_output], error_output=None)
        events = list(sender)
        assert len(events) == 3, "only logevents should be returned"
        assert all(isinstance(event, LogEvent) for event in events)
        assert len(opensearch_output.events) == 4, "3 events + 1 extra data event"
        assert all(event.state == EventStateType.DELIVERED for event in opensearch_output.events)
