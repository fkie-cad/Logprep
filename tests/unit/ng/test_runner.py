# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
import pytest

from logprep.factory import Factory
from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent
from logprep.ng.pipeline import Pipeline
from logprep.ng.runner import Runner
from logprep.ng.sender import Sender
from logprep.util.configuration import Configuration


@pytest.fixture(name="input_connector")
def get_input_mock():
    return iter(
        [
            LogEvent({"message": "Log message 1"}, original=b"", state=EventStateType.RECEIVED),
            LogEvent({"message": "Log message 2"}, original=b"", state=EventStateType.RECEIVED),
            LogEvent({"user": {"name": "John Doe"}}, original=b"", state=EventStateType.RECEIVED),
        ]
    )


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
def get_pipeline_mock(
    input_connector,
):
    """Create a mock for the Pipeline class."""
    return Pipeline(input_connector, processors)


@pytest.fixture(name="sender")
def get_sender_mock(pipeline, kafka_output, opensearch_output, error_output):
    """Create a mock for the Sender class."""
    return Sender(
        pipeline=pipeline, outputs=[kafka_output, opensearch_output], error_output=error_output
    )


@pytest.fixture(name="configuration")
def get_logprep_config():
    config_dict = {
        "pipeline": [
            {
                "processor_0": {
                    "type": "ng_generic_adder",
                    "rules": [
                        {
                            "filter": "*",
                            "generic_adder": {"add": {"event.tags": "generic added tag"}},
                        }
                    ],
                }
            },
            {
                "processor_1": {
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
            },
        ],
        "output": {
            "kafka": {
                "type": "ng_dummy_output",
                "default": False,
            },
            "opensearch": {
                "type": "ng_dummy_output",
            },
        },
        "error_output": {
            "error": {
                "type": "ng_dummy_output",
            }
        },
    }
    return Configuration(**config_dict)


class TestRunner:

    def test_from_configuration(self, configuration):
        runner = Runner.from_configuration(configuration)
        assert isinstance(runner, Runner)
        assert isinstance(runner.sender, Sender)

    def test_from_configuration_runs_setup(self, configuration):
        assert False

    def test_stop_injects_sentinel(self, configuration):
        runner = Runner.from_configuration(configuration)
        runner.stop()
        assert runner.should_exit is True

    def test_run_stops_on_sentinel(self, configuration):
        runner = Runner.from_configuration(configuration)
        runner.stop()
        runner.run()
        assert runner.should_exit is True
