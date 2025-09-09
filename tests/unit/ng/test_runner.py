# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
from unittest import mock

import pytest

from logprep.ng.abc.event import EventBacklog
from logprep.ng.runner import Runner
from logprep.ng.sender import LogprepReloadException, Sender
from logprep.util.configuration import Configuration


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


@mock.patch("logprep.ng.runner.QueueListener", new=mock.MagicMock())
class TestRunner:

    def teardown_method(self):
        Runner.instance = None

    def test_from_configuration(self, configuration):
        runner = Runner.from_configuration(configuration)
        assert isinstance(runner, Runner)
        assert isinstance(runner.sender, Sender)
        assert isinstance(runner._input_connector.event_backlog, EventBacklog)

    def test_from_configuration_runs_setup(self, configuration):
        with mock.patch.object(Runner, "setup") as mock_setup:
            Runner.from_configuration(configuration)
            mock_setup.assert_called_once()

    def test_setup_calls_sender_setup(self, configuration):
        runner = Runner.from_configuration(configuration)
        with mock.patch.object(runner.sender, "setup") as mock_sender_setup:
            runner.setup()
            mock_sender_setup.assert_called_once()

    def test_setup_calls_input_connector_setup(self, configuration):
        runner = Runner.from_configuration(configuration)
        with mock.patch.object(runner._input_connector, "setup") as mock_input_setup:
            runner.setup()
            mock_input_setup.assert_called_once()

    def test_stop_raises_system_exit(self, configuration):
        runner = Runner.from_configuration(configuration)
        with pytest.raises(SystemExit, match="0"):
            runner.stop()

    @mock.patch("logging.getLogger")
    def test_shutdown_stops_logger(self, _, configuration):
        runner = Runner.from_configuration(configuration)
        with mock.patch.object(runner, "_log_handler") as mock_log_handler:
            runner.shut_down()
            mock_log_handler.stop.assert_called_once()

    def test_shut_down_calls_input_connector_shut_down(self, configuration):
        runner = Runner.from_configuration(configuration)
        with mock.patch.object(runner._input_connector, "shut_down") as mock_input_shut_down:
            runner.shut_down()
            mock_input_shut_down.assert_called_once()

    @mock.patch("logging.getLogger")
    def test_init_setups_logging(self, mock_get_logger):
        _ = Runner(mock.MagicMock())
        mock_get_logger.assert_called_once_with("console")

    def test_reload_calls_sender_shut_down(self, configuration):
        runner = Runner.from_configuration(configuration)
        with mock.patch.object(runner.sender, "shut_down") as mock_sender_shut_down:
            runner.reload()
            mock_sender_shut_down.assert_called_once()

    def test_reload_starts_new_sender(self, configuration):
        runner = Runner.from_configuration(configuration)
        old_sender = runner.sender
        runner.reload()
        assert runner.sender is not old_sender

    def test_reload_setups_sender(self, configuration):
        runner = Runner.from_configuration(configuration)
        new_sender = mock.MagicMock()
        with mock.patch.object(Runner, "get_sender", return_value=new_sender):
            runner.reload()
        new_sender.setup.assert_called_once()

    def test_reload_setups_new_input(self, configuration):
        runner = Runner.from_configuration(configuration)
        with mock.patch.object(Runner, "get_sender", return_value=mock.MagicMock()):
            with mock.patch.object(runner._input_connector, "setup") as mock_input_setup:
                runner.reload()
                mock_input_setup.assert_called_once()

    def test_reload_schedules_new_config_refresh_job(self, configuration):
        runner = Runner.from_configuration(configuration)
        with mock.patch(
            "logprep.util.configuration.Configuration.schedule_config_refresh"
        ) as mock_schedule:
            runner.reload()
            mock_schedule.assert_called_once()

    def test_run_calls_reload_on_reload_exception(self, configuration):
        runner = Runner.from_configuration(configuration)
        with mock.patch.object(runner, "_process_events", side_effect=LogprepReloadException()):
            with mock.patch.object(runner, "reload") as mock_reload:
                mock_reload.side_effect = SystemExit(666)
                with pytest.raises(SystemExit, match="666"):
                    runner.run()
