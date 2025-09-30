# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import os
from unittest import mock

import pytest

from logprep.ng.event.event_state import EventStateType
from logprep.ng.runner import Runner
from logprep.ng.util.configuration import Configuration


@pytest.fixture(name="configuration")
def get_logprep_config():
    config_dict = {
        "process_count": 2,
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

    def teardown_method(self):
        Runner.instance = None

    def test_runner_init_calls_setup(self, configuration):
        with mock.patch.object(Runner, "setup") as mock_setup:
            Runner(configuration)
            mock_setup.assert_called_once()

    def test_setup_calls_initialize_and_setup_sender(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner, "setup") as runner_setup:
            runner.setup()
            runner_setup._initialize_and_setup_sender.cassert_called_once()

    def test_setup_calls_initialize_and_setup_input_connectors(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner, "setup") as runner_setup:
            runner.setup()
            runner_setup._initialize_and_setup_input_connectors.cassert_called_once()

    def test_setup_calls_initialize_and_setup_output_connectors(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner, "setup") as runner_setup:
            runner.setup()
            runner_setup._initialize_and_setup_output_connectors.cassert_called_once()

    def test_setup_calls_initialize_and_setup_error_outputs(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner, "setup") as runner_setup:
            runner.setup()
            runner_setup._initialize_and_setup_error_outputs.cassert_called_once()

    def test_setup_calls_initialize_and_setup_processors(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner, "setup") as runner_setup:
            runner.setup()
            runner_setup._initialize_and_setup_processors.cassert_called_once()

    def test_setup_calls_initialize_and_setup_pipeline(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner, "setup") as runner_setup:
            runner.setup()
            runner_setup._initialize_and_setup_pipeline.cassert_called_once()

    def test_shut_down_calls_input_connector_shut_down(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner.input_connector, "shut_down") as mock_input_shut_down:
            runner.shut_down()
            mock_input_shut_down.assert_called_once()

    def test_reload_calls_sender_shut_down(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner.sender, "shut_down") as mock_sender_shut_down:
            runner.reload()
            mock_sender_shut_down.assert_called_once()

    def test_reload_starts_new_sender(self, configuration):
        runner = Runner(configuration)
        old_sender = runner.sender
        runner.reload()
        assert runner.sender is not old_sender

    def test_reload_setups_sender(self, configuration):
        runner = Runner(configuration)
        new_sender = mock.MagicMock()
        with mock.patch.object(Runner, "get_sender", return_value=new_sender):
            runner.reload()
        new_sender.setup.assert_called_once()

    def test_reload_setups_new_input(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(Runner, "get_sender", return_value=mock.MagicMock()):
            with mock.patch.object(runner.input_connector, "setup") as mock_input_setup:
                runner.reload()
                mock_input_setup.assert_called_once()

    def test_reload_schedules_new_config_refresh_job(self, configuration):
        runner = Runner(configuration)
        with mock.patch(
            "logprep.ng.util.configuration.Configuration.schedule_config_refresh"
        ) as mock_schedule:
            runner.reload()
            mock_schedule.assert_called_once()

    def test_process_events_iterates_sender(self, configuration, caplog):
        caplog.set_level("DEBUG")
        sender = mock.MagicMock()
        sender.__iter__.return_value = [
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
        ]
        runner = Runner(sender)
        runner._configuration = configuration
        runner.sender = sender

        assert runner

        runner._process_events()

        assert len(caplog.text.splitlines()) == 8, "all events processed plus start and end logs"
        assert "event processed" in caplog.text

    def test_process_events_refreshes_configuration(self):
        sender = mock.MagicMock()
        sender.__iter__.return_value = [
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
        ]
        runner = Runner(sender)
        runner._configuration = mock.MagicMock()

        assert runner

        runner._process_events()
        runner._configuration.refresh.assert_called()
        assert runner._configuration.refresh.call_count == 4

    def test_process_events_logs_failed_event_on_debug(self, caplog):
        caplog.set_level("DEBUG")
        sender = mock.MagicMock()
        failing_event = mock.MagicMock()
        failing_event.state = EventStateType.FAILED
        sender.__iter__.return_value = [
            mock.MagicMock(),
            failing_event,
            mock.MagicMock(),
            mock.MagicMock(),
        ]

        runner = Runner(sender)
        runner._configuration = mock.MagicMock()

        assert runner
        runner._process_events()
        assert "event failed" in caplog.text, "one event failed"
        assert "event processed" in caplog.text, "other events processed"

    def test_setup_logging_emits_env(self, configuration):
        runner = Runner(configuration)
        assert not os.environ.get("LOGPREP_LOG_CONFIG")
        runner.setup_logging()
        assert os.environ.get("LOGPREP_LOG_CONFIG")

    def test_setup_logging_calls_dict_config(self, configuration):
        runner = Runner(configuration)
        with mock.patch("logging.config.dictConfig") as mock_dict_config:
            runner.setup_logging()
            mock_dict_config.assert_called_once()

    def test_setup_logging_captures_warnings(self, configuration):
        runner = Runner(configuration)
        with mock.patch("logging.captureWarnings") as mock_capture_warnings:
            runner.setup_logging()
            mock_capture_warnings.assert_called_once_with(True)

    def test_setup_logging_sets_filter(self, configuration):
        runner = Runner(configuration)
        with mock.patch("warnings.simplefilter") as mock_simplefilter:
            runner.setup_logging()
            mock_simplefilter.assert_called_once_with("always", DeprecationWarning)

    def test_stop_method(self, configuration):
        runner = Runner(configuration)
        runner.stop()
        runner.run()

        assert runner.should_exit

    def test_process_none_event(self, configuration):
        sender = mock.MagicMock()
        sender.__iter__.return_value = [
            None,
        ]

        runner = Runner(sender)
        runner._configuration = mock.MagicMock()
        runner._configuration.refresh = mock.MagicMock()

        runner._process_events()

        assert runner._configuration.refresh.call_count == 1
