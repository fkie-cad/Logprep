# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import logging
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
        "logger": {
            "version": 1,
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                }
            },
            "loggers": {
                "Runner": {"level": "DEBUG", "handlers": ["console"], "propagate": True},
                "root": {"level": "DEBUG", "handlers": ["console"]},
            },
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
        with mock.patch.object(runner, "input_connector") as mock_input_connector:
            runner.shut_down()
            mock_input_connector.shut_down.cassert_called_once()

    def test_shut_down_calls_output_connector_shut_down(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner, "output_connector") as mock_output_connector:
            runner.shut_down()
            mock_output_connector.shut_down.cassert_called_once()

    def test_shut_down_calls_error_output_shut_down(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner, "error_output") as mock_error_output:
            runner.shut_down()
            mock_error_output.shut_down.cassert_called_once()

    def test_shut_down_calls_processors_shut_down(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner, "processors") as mock_processors:
            runner.shut_down()
            assert mock_processors.call_count == len(runner.processors)

    def test_shut_down_calls_pipeline_shut_down(self, configuration):
        runner = Runner(configuration)
        with mock.patch.object(runner, "pipeline") as mock_pipeline:
            runner.shut_down()
            mock_pipeline.shut_down.cassert_called_once()

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

    def test_reload_setups_new_input(self, configuration):
        runner = Runner(configuration)
        runner_input_connector = runner.input_connector

        with mock.patch.object(
            runner, "_initialize_and_setup_input_connectors"
        ) as mock_init_input_connectors:
            runner.reload()
            assert runner.input_connector is runner_input_connector
            mock_init_input_connectors.assert_called_once()

    def test_reload_schedules_new_config_refresh_job(self, configuration):
        runner = Runner(configuration)
        with mock.patch(
            "logprep.ng.util.configuration.Configuration.schedule_config_refresh"
        ) as mock_schedule:
            runner.reload()
            mock_schedule.assert_called_once()

    def test_process_events_iterates_sender(self, caplog, configuration):
        caplog.set_level("DEBUG")

        sender = mock.MagicMock()
        sender.__iter__.return_value = [
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
        ]
        runner = Runner(configuration)
        runner.sender = sender

        assert runner

        runner._process_events()

        assert len(caplog.text.splitlines()) == 25, "all events processed plus start and end logs"
        assert "event processed" in caplog.text

    def test_run_refreshes_configuration(self, configuration):
        sender = mock.MagicMock()
        sender.__iter__.return_value = [
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
        ]
        runner = Runner(configuration)
        runner.sender = sender
        runner._process_events = mock.MagicMock()
        assert runner

        configuration.version = "set"

        with mock.patch.object(Configuration, "refresh", autospec=True) as mock_refresh:
            mock_refresh.side_effect = lambda _: setattr(runner, "should_exit", True)

            runner.run()
            mock_refresh.assert_called_with(configuration)
            assert mock_refresh.call_count == 2

    def test_process_events_logs_failed_event_on_debug(self, caplog, configuration):
        caplog.set_level("DEBUG")
        failing_event = mock.MagicMock()
        failing_event.state = EventStateType.FAILED

        runner = Runner(configuration)

        with mock.patch.object(runner, "sender") as mock_sender:
            mock_sender.__iter__.return_value = [
                mock.MagicMock(),
                failing_event,
                mock.MagicMock(),
            ]

            with caplog.at_level("DEBUG", logger="Runner"):
                runner._process_events()

                runner_logs = [
                    rec.getMessage().lower() for rec in caplog.records if rec.name == "Runner"
                ]
                assert any("event failed" in msg for msg in runner_logs)
                assert any("event processed" in msg for msg in runner_logs)

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

        runner = Runner(configuration)

        with mock.patch.object(Configuration, "refresh", autospec=True) as mock_refresh:
            mock_refresh.side_effect = lambda _: setattr(runner, "should_exit", True)

            runner.run()
            mock_refresh.assert_called_with(configuration)
            assert mock_refresh.call_count == 1
