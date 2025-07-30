# pylint: disable=missing-docstring
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


@pytest.fixture(name="pipeline")
def get_pipeline_mock(input_connector, processors):
    """Create a mock for the Pipeline class."""
    return Pipeline(input_connector, processors)


class TestSender:
    """Test the Sender class."""

    def test_sender_initialization(self, pipeline):
        sender = Sender(pipeline=pipeline, outputs=[], error_output=None)
        assert sender
