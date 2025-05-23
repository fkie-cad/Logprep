# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import logging
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path
from unittest import mock

import pytest
import requests
import responses
from click.testing import CliRunner
from ruamel.yaml import YAML

from logprep import run_logprep
from logprep.run_logprep import cli
from logprep.util.configuration import Configuration, InvalidConfigurationError
from logprep.util.defaults import EXITCODES


class TestRunLogprepCli:
    def setup_method(self):
        self.cli_runner = CliRunner()

    @pytest.mark.parametrize(
        "command, target",
        [
            ("run tests/testdata/config/config.yml", "logprep.run_logprep.Runner.start"),
            (
                "test config tests/testdata/config/config.yml",
                "logprep.run_logprep._get_configuration",
            ),
            (
                "print tests/testdata/config/config.yml",
                "logprep.util.configuration.Configuration.as_yaml",
            ),
            (
                "run tests/testdata/config/config.yml tests/testdata/config/config.yml",
                "logprep.run_logprep.Runner.start",
            ),
            (
                "test config tests/testdata/config/config.yml tests/testdata/config/config.yml",
                "logprep.run_logprep._get_configuration",
            ),
            (
                "print tests/testdata/config/config.yml tests/testdata/config/config.yml",
                "logprep.util.configuration.Configuration.as_yaml",
            ),
            (
                "test dry-run tests/testdata/config/config.yml examples/exampledata/input_logdata/test_input.jsonl",
                "logprep.util.rule_dry_runner.DryRunner.run",
            ),
            (
                "test dry-run tests/testdata/config/config.yml tests/testdata/config/config.yml asdfsdv",
                "logprep.util.rule_dry_runner.DryRunner.run",
            ),
        ],
    )
    def test_cli_commands_with_configs(self, command: str, target: str):
        with mock.patch(target) as mocked_target:
            result = self.cli_runner.invoke(cli, command.split())
        mocked_target.assert_called()
        assert result.exit_code == 0, f"{result.exc_info}"

    @pytest.mark.parametrize(
        "command",
        [
            ("run",),
            ("test", "config"),
            ("test", "unit"),
            ("test", "dry-run", "input_data"),
        ],
    )
    def test_cli_invokes_default_config_location(self, command, caplog):
        result = self.cli_runner.invoke(cli, [*command])
        assert result.exit_code != 0
        assert "does not exist: /etc/logprep/pipeline.yml" in caplog.text

    @mock.patch("logprep.run_logprep.Runner")
    def test_cli_run_starts_runner_with_config(self, mock_runner):
        runner_instance = mock.MagicMock()
        config_file_path = ("tests/testdata/config/config.yml",)
        expected_config = Configuration.from_sources(config_file_path)
        mock_runner.get_runner.return_value = runner_instance
        args = ["run", *config_file_path]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        mock_runner.get_runner.assert_called_with(expected_config)
        runner_instance.start.assert_called()

    @mock.patch("logprep.run_logprep.Runner")
    def test_cli_run_starts_runner_with_multiple_configs(self, mock_runner):
        runner_instance = mock.MagicMock()
        mock_runner.get_runner.return_value = runner_instance
        config_file_path = ("tests/testdata/config/config.yml", "tests/testdata/config/config.yml")
        expected_config = Configuration.from_sources(config_file_path)
        args = ["run", *config_file_path]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        mock_runner.get_runner.assert_called_with(expected_config)
        runner_instance.start.assert_called()

    def test_exits_after_getter_error_for_not_existing_protocol(self, caplog):
        args = ["run", "almighty_protocol://tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == EXITCODES.CONFIGURATION_ERROR.value
        assert "No getter for protocol 'almighty_protocol'" in caplog.text

    @mock.patch("logprep.util.configuration.Configuration._verify")
    def test_test_config_verifies_configuration_successfully(self, mock_verify):
        args = ["test", "config", "tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == EXITCODES.SUCCESS.value
        mock_verify.assert_called()
        assert "The verification of the configuration was successful" in result.stdout

    @mock.patch("logprep.run_logprep.LogprepMPQueueListener")
    def test_listener_start_and_stop_called(self, mock_listener_cls):
        mock_listener = mock.Mock()
        mock_listener_cls.return_value = mock_listener

        args = ["test", "config", "tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)

        assert mock_listener.start.called, "Listener start() was not called"
        assert mock_listener.stop.called, "Listener stop() was not called"

    @mock.patch("logprep.util.configuration.Configuration._verify")
    def test_test_config_verifies_configuration_unsuccessfully(self, mock_verify):
        mock_verify.side_effect = InvalidConfigurationError("test error")
        args = ["test", "config", "tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == EXITCODES.CONFIGURATION_ERROR.value
        mock_verify.assert_called()
        assert "The verification of the configuration was successful" not in result.stdout

    @responses.activate
    def test_gets_config_from_https(self):
        pipeline_config = Path("tests/testdata/config/config.yml").read_text(encoding="utf8")
        responses.add(responses.GET, "https://does.not.exits/pipline.yml", pipeline_config)
        args = ["test", "config", "https://does.not.exits/pipline.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0

    def test_version_arg_prints_logprep_version(self):
        result = self.cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {version('logprep')}" in result.output
        assert "configuration version:   no configuration found" in result.output

    def test_run_version_arg_prints_logprep_version_with_config_version(self):
        args = ["run", "--version", "tests/testdata/config/config.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {version('logprep')}" in result.output
        assert (
            "configuration version:   1, file://tests/testdata/config/config.yml" in result.output
        )

    def test_run_version_arg_prints_logprep_version_without_config_value(self):
        args = ["run", "--version", "tests/testdata/config/config2.yml"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {version('logprep')}" in result.output
        assert (
            "configuration version:   alternative, file://tests/testdata/config/config2.yml"
            in result.output
        )

    @responses.activate
    def test_run_version_arg_prints_with_http_config(self):
        config_path = "tests/testdata/config/config.yml"
        responses.add(
            responses.GET,
            f"http://localhost:32000/{config_path}",
            Path(config_path).read_text(encoding="utf8"),
        )
        args = ["run", "--version", f"http://localhost:32000/{config_path}"]
        result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {version('logprep')}" in result.output
        assert f"configuration version:   1, http://localhost:32000/{config_path}" in result.output

    @responses.activate
    def test_run_version_arg_prints_with_http_config_without_exposing_secret_data(self):
        config_path = "tests/testdata/config/config.yml"
        mock_env = {
            "LOGPREP_CONFIG_AUTH_USERNAME": "username",
            "LOGPREP_CONFIG_AUTH_PASSWORD": "password",
        }
        responses.add(
            responses.GET,
            f"http://localhost:32000/{config_path}",
            Path(config_path).read_text(encoding="utf8"),
        )
        args = ["run", "--version", f"http://localhost:32000/{config_path}"]
        with mock.patch("os.environ", mock_env):
            result = self.cli_runner.invoke(cli, args)
        assert result.exit_code == 0
        assert f"python version:          {sys.version.split()[0]}" in result.output
        assert f"logprep version:         {version('logprep')}" in result.output
        assert f"configuration version:   1, http://localhost:32000/{config_path}" in result.output
        assert "username" not in result.output
        assert "password" not in result.output

    def test_run_no_config_error_is_printed_if_given_config_file_does_not_exist(self, caplog):
        non_existing_config_file = "/tmp/does/not/exist.yml"
        result = self.cli_runner.invoke(cli, ["run", non_existing_config_file])
        assert result.exit_code == EXITCODES.CONFIGURATION_ERROR.value
        expected_lines = (
            f"One or more of the given config file(s) does not exist: "
            f"{non_existing_config_file}\n"
        )
        assert expected_lines in caplog.text

    @mock.patch("logprep.runner.Runner._runner")
    def test_main_calls_runner_stop_on_any_exception(self, mock_runner):
        mock_runner.start.side_effect = Exception
        config_path = "tests/testdata/config/config.yml"
        result = self.cli_runner.invoke(cli, ["run", config_path])
        assert result.exit_code == 1
        mock_runner.stop.assert_called()

    def test_logprep_exits_on_invalid_configuration(self):
        with mock.patch("logprep.util.configuration.Configuration._verify") as mock_verify:
            mock_verify.side_effect = InvalidConfigurationError("test error")
            config_path = "tests/testdata/config/config.yml"
            result = self.cli_runner.invoke(cli, ["run", config_path])
            assert result.exit_code == EXITCODES.CONFIGURATION_ERROR.value

    def test_logprep_exits_on_any_exception_during_verify(self):
        with mock.patch("logprep.util.configuration.Configuration._verify") as mock_verify:
            mock_verify.side_effect = Exception
            config_path = "tests/testdata/config/config.yml"
            result = self.cli_runner.invoke(cli, ["run", config_path])
            assert result.exit_code == 1

    def test_logprep_exits_on_request_exception(self):
        with mock.patch("logprep.util.getter.HttpGetter.get_raw") as mock_verify:
            mock_verify.side_effect = requests.RequestException("connection refused")
            config_path = "http://localhost/does-not-exists"
            result = self.cli_runner.invoke(cli, ["run", config_path])
            assert result.exit_code == EXITCODES.CONFIGURATION_ERROR.value

    @mock.patch("logprep.util.rule_dry_runner.DryRunner.run")
    def test_test_dry_run_starts_dry_runner(self, mock_dry_runner):
        config_path = ("tests/testdata/config/config.yml",)
        events_path = "examples/exampledata/input_logdata/test_input.jsonl"
        result = self.cli_runner.invoke(cli, ["test", "dry-run", *config_path, events_path])
        assert result.exit_code == 0
        mock_dry_runner.assert_called()

    @mock.patch("logprep.util.auto_rule_tester.auto_rule_tester.AutoRuleTester.run")
    def test_test_rules_starts_auto_rule_tester(self, mock_tester):
        config_path = "tests/testdata/config/config.yml"
        result = self.cli_runner.invoke(cli, ["test", "unit", config_path])
        assert result.exit_code == 0
        mock_tester.assert_called()
        # the AutoRuleTester deactivates the logger which then has side effects on other tests
        # so the logger is being activated here again.
        logger = logging.getLogger()
        logger.disabled = False

    @mock.patch("logging.Logger.info")
    def test_run_logprep_logs_log_level(self, mock_info):
        config = Configuration.from_sources(("tests/testdata/config/config.yml",))
        assert config.logger.level == "INFO"
        with mock.patch("logprep.run_logprep.Runner"):
            with pytest.raises(SystemExit):
                run_logprep.run(("tests/testdata/config/config.yml",))
        mock_info.assert_has_calls([mock.call("Log level set to '%s'", "INFO")])


class TestGeneratorCLI:
    @pytest.mark.parametrize(
        "create_path, command_args, expected_kwargs",
        [
            (
                "logprep.generator.factory.ControllerFactory.create",
                [
                    "generate",
                    "http",
                    "--input-dir",
                    "/some-path",
                    "--target-url",
                    "some-domain",
                    "--user",
                    "user",
                    "--events",
                    "1000",
                    "--password",
                    "password",
                ],
                {
                    "target": "http",
                    "input_dir": "/some-path",
                    "target_url": "some-domain",
                    "user": "user",
                    "password": "password",
                    "batch_size": 500,
                    "events": 1000,
                    "shuffle": False,
                    "thread_count": 1,
                    "replace_timestamp": True,
                    "tag": "loadtest",
                    "loglevel": "INFO",
                    "timeout": 2,
                    "verify": "False",
                },
            ),
            (
                "logprep.generator.factory.ControllerFactory.create",
                [
                    "generate",
                    "kafka",
                    "--input-dir",
                    "/some-path",
                    "--output-config",
                    '{"bootstrap.servers": "localhost:9092"}',
                    "--user",
                    "user",
                    "--events",
                    "1000",
                    "--password",
                    "password",
                ],
                {
                    "target": "kafka",
                    "input_dir": "/some-path",
                    "output_config": '{"bootstrap.servers": "localhost:9092"}',
                    "user": "user",
                    "password": "password",
                    "batch_size": 500,
                    "events": 1000,
                    "shuffle": False,
                    "thread_count": 1,
                    "replace_timestamp": True,
                    "tag": "loadtest",
                    "loglevel": "INFO",
                    "send_timeout": 0,
                },
            ),
        ],
    )
    def test_generator_cli_runs_generator_with_default_values(
        self, create_path, command_args, expected_kwargs
    ):

        runner = CliRunner()
        with mock.patch(create_path) as mock_create:
            mock_controller_instance = mock.Mock()
            mock_create.return_value = mock_controller_instance

            result = runner.invoke(cli, command_args)
            mock_create.assert_called_once_with(**expected_kwargs)
            mock_controller_instance.run.assert_called_once()
            assert result.exit_code == 0

    @pytest.mark.parametrize(
        "create_path, command_args, expected_kwargs",
        [
            (
                "logprep.generator.factory.ControllerFactory.create",
                [
                    "generate",
                    "http",
                    "--input-dir",
                    "/some-path",
                    "--target-url",
                    "some-domain",
                    "--user",
                    "user",
                    "--password",
                    "password",
                    "--events",
                    "5000",
                    "--shuffle",
                    "False",
                    "--thread-count",
                    "2",
                    "--batch-size",
                    "1000",
                    "--replace-timestamp",
                    "False",
                    "--tag",
                    "test-tag",
                    "--loglevel",
                    "DEBUG",
                    "--verify",
                    "/test/path",
                ],
                {
                    "target": "http",
                    "input_dir": "/some-path",
                    "target_url": "some-domain",
                    "user": "user",
                    "password": "password",
                    "batch_size": 1000,
                    "events": 5000,
                    "shuffle": False,
                    "thread_count": 2,
                    "replace_timestamp": False,
                    "tag": "test-tag",
                    "loglevel": "DEBUG",
                    "timeout": 2,
                    "verify": "/test/path",
                },
            ),
            (
                "logprep.generator.factory.ControllerFactory.create",
                [
                    "generate",
                    "kafka",
                    "--input-dir",
                    "/some-path",
                    "--output-config",
                    '{"bootstrap.servers": "localhost:9092"}',
                    "--user",
                    "user",
                    "--password",
                    "password",
                    "--events",
                    "5000",
                    "--shuffle",
                    "False",
                    "--thread-count",
                    "2",
                    "--batch-size",
                    "1000",
                    "--replace-timestamp",
                    "False",
                    "--tag",
                    "test-tag",
                    "--loglevel",
                    "DEBUG",
                ],
                {
                    "target": "kafka",
                    "input_dir": "/some-path",
                    "output_config": '{"bootstrap.servers": "localhost:9092"}',
                    "user": "user",
                    "password": "password",
                    "events": 5000,
                    "shuffle": False,
                    "thread_count": 2,
                    "batch_size": 1000,
                    "replace_timestamp": False,
                    "tag": "test-tag",
                    "loglevel": "DEBUG",
                    "send_timeout": 0,
                },
            ),
        ],
    )
    def test_generator_cli_overwrites_default_values(
        self, create_path, command_args, expected_kwargs
    ):
        runner = CliRunner()
        with mock.patch(create_path) as mock_create:
            mock_controller_instance = mock.Mock()
            mock_create.return_value = mock_controller_instance

            result = runner.invoke(cli, command_args)
            mock_create.assert_called_once_with(**expected_kwargs)
            mock_controller_instance.run.assert_called_once()
            assert result.exit_code == 0


class TestPseudoCLI:

    @pytest.mark.parametrize("mode", ["gcm", "ctr"])
    def test_pseudonymize_depseudonymize_with_mode(self, mode, tmp_path):
        (tmp_path / "analyst").touch()
        (tmp_path / "depseudo").touch()

        runner = CliRunner()
        result = runner.invoke(cli, ["pseudo", "generate", "-f", f"{tmp_path}/analyst", "1024"])
        assert result.exit_code == 0
        result = runner.invoke(cli, ["pseudo", "generate", "-f", f"{tmp_path}/depseudo", "2048"])
        assert result.exit_code == 0
        result = runner.invoke(
            cli,
            [
                "pseudo",
                "pseudonymize",
                "--mode",
                f"{mode}",
                f"{tmp_path}/analyst.crt",
                f"{tmp_path}/depseudo.crt",
                "string",
            ],
        )
        assert result.exit_code == 0, result.output
        pseudonymized_string = result.output.strip()
        result = runner.invoke(
            cli,
            [
                "pseudo",
                "depseudonymize",
                "--mode",
                f"{mode}",
                f"{tmp_path}/analyst.key",
                f"{tmp_path}/depseudo.key",
                f"{pseudonymized_string}",
            ],
        )
        assert result.exit_code == 0
        assert result.output.strip() == "string"


class TestYamlLoaderTags:
    def test_yaml_loader_include_tag_initialized(self, tmp_path):
        yaml = YAML(pure=True, typ="safe")
        path_to_file_to_include = self._write_to_yaml_file("this: was included", tmp_path)
        yml_with_tag = f"""
        foo:
            bar: !include {path_to_file_to_include}
        """
        yaml_file = self._write_to_yaml_file(yml_with_tag, tmp_path)
        with open(yaml_file, "r", encoding="utf-8") as file:
            loaded = yaml.load(file)
        assert loaded["foo"]["bar"] == {"this": "was included"}

    @staticmethod
    def _write_to_yaml_file(file_content: str, target_directory: Path):
        rule_file = tempfile.mktemp(dir=target_directory, suffix=".yml")
        with open(rule_file, "w", encoding="utf-8") as file:
            file.write(file_content)
        return rule_file
