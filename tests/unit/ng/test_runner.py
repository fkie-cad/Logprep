# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
from unittest import mock

import pytest

from logprep.factory import Factory
from logprep.ng.abc.event import EventBacklog
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
        "input": {"file": {"type": "ng_dummy_input", "documents": []}},
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
        assert isinstance(runner._input_connector.event_backlog, EventBacklog)

    def test_from_configuration_runs_setup(self, configuration):
        assert False

    def test_stop_raises_system_exit(self, configuration):
        runner = Runner.from_configuration(configuration)
        with pytest.raises(SystemExit, match="0"):
            runner.stop()

    def test_stop_calls_shutdown(self, configuration):
        with mock.patch("logprep.ng.runner.Runner.shut_down") as mock_shutdown:
            runner = Runner.from_configuration(configuration)
            with pytest.raises(SystemExit, match="0"):
                runner.stop()
        mock_shutdown.assert_called_once()
