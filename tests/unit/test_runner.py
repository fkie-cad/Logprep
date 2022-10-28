# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=no-self-use
from copy import deepcopy
from logging import Logger, ERROR, INFO
from os.path import split, join

from pytest import raises

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.labeler.labeling_schema import (
    LabelingSchemaError,
)
from logprep.runner import (
    Runner,
    MustNotConfigureTwiceError,
    MustConfigureBeforeRunningError,
    CannotReloadWhenConfigIsUnsetError,
    NotALoggerError,
    MustConfigureALoggerError,
    MustNotSetLoggerTwiceError,
    UseGetRunnerToCreateRunnerSingleton,
    MustNotCreateMoreThanOneManagerError,
)
from tests.testdata.ConfigurationForTest import ConfigurationForTest
from tests.testdata.metadata import (
    path_to_config,
    path_to_alternative_config,
    path_to_invalid_config,
    path_to_invalid_rules,
    path_to_schema2,
)
from tests.unit.framework.test_pipeline_manager import PipelineManagerForTesting
from tests.util.testhelpers import HandlerStub, AssertEmitsLogMessage


class RunnerForTesting(Runner):
    def __init__(self):
        super().__init__(bypass_check_to_obtain_non_singleton_instance=True)

    def _create_manager(self):
        self._manager = PipelineManagerForTesting(self._logger, self._metric_targets)


class LogprepRunnerTest:
    def setup_method(self, _):
        self.handler = HandlerStub()
        self.logger = Logger("test")
        self.logger.addHandler(self.handler)

        self.runner = RunnerForTesting()
        self.runner.set_logger(self.logger)
        self.runner._create_manager()


class TestRunnerExpectedFailures(LogprepRunnerTest):
    def test_init_fails_when_bypass_check_flag_is_not_set(self):
        with raises(UseGetRunnerToCreateRunnerSingleton):
            Runner()

    def test_fails_when_calling_create_manager_more_than_once(self):
        runner = Runner(bypass_check_to_obtain_non_singleton_instance=True)
        runner.set_logger(self.logger)
        runner.load_configuration(path_to_config)

        runner._create_manager()
        with raises(MustNotCreateMoreThanOneManagerError):
            runner._create_manager()

    def test_fails_when_calling_load_configuration_with_non_existing_path(self):
        with raises(FileNotFoundError):
            self.runner.load_configuration("non-existing-file")

    def test_fails_when_calling_load_configuration_more_than_once(self):
        self.runner.load_configuration(path_to_config)

        with raises(MustNotConfigureTwiceError):
            self.runner.load_configuration(path_to_config)

    def test_fails_when_called_without_configuring_first(self):
        with raises(MustConfigureBeforeRunningError):
            self.runner.start()

    def test_fails_when_setting_logger_to_non_logger_object(self):
        for non_logger in [None, "string", 123, 45.67, TestRunner()]:
            with raises(NotALoggerError):
                self.runner.set_logger(non_logger)

    def test_fails_when_setting_logger_twice(self):
        with raises(MustNotSetLoggerTwiceError):
            self.runner.set_logger(Logger("test"))

    def test_fails_when_starting_without_setting_logger_first(self):
        self.runner.load_configuration(path_to_config)
        self.runner._logger = None

        with raises(MustConfigureALoggerError):
            self.runner.start()

    def test_fails_when_rules_are_invalid(self):
        with raises(InvalidRuleDefinitionError, match=r"no filter defined"):
            with ConfigurationForTest(
                inject_changes=[
                    {
                        "pipeline": {
                            1: {
                                "labelername": {
                                    "specific_rules": [path_to_invalid_rules],
                                    "generic_rules": [path_to_invalid_rules],
                                }
                            }
                        }
                    }
                ]
            ) as path:
                self.runner.load_configuration(path)

    def test_fails_when_schema_and_rules_are_inconsistent(self):
        with raises(LabelingSchemaError):
            with ConfigurationForTest(
                inject_changes=[{"pipeline": {1: {"labelername": {"schema": path_to_schema2}}}}]
            ) as path:
                self.runner.load_configuration(path)

    def test_fails_when_calling_reload_configuration_when_config_is_unset(self):
        with raises(CannotReloadWhenConfigIsUnsetError):
            self.runner.reload_configuration()


class TestRunner(LogprepRunnerTest):
    def setup_method(self, _):
        self.handler = HandlerStub()
        self.logger = Logger("test")
        self.logger.addHandler(self.handler)

        self.runner = RunnerForTesting()
        self.runner.set_logger(self.logger)
        self.runner.load_configuration(path_to_config)
        self.runner._create_manager()

    def test_get_runner_returns_the_same_runner_on_all_calls(self):
        runner = Runner.get_runner()

        for _ in range(10):
            assert runner == Runner.get_runner()

    def test_reload_configuration_logs_info_when_reloading_config_was_successful(self):
        with AssertEmitsLogMessage(self.handler, INFO, "Successfully reloaded configuration"):
            self.runner.reload_configuration()

    def test_reload_configuration_reduces_logprep_instance_count_to_new_value(self):
        self.runner._manager.set_count(3)

        self.runner._yaml_path = path_to_alternative_config
        self.runner.reload_configuration()
        assert self.runner._manager.get_count() == 2

    def test_reload_configuration_leaves_old_configuration_in_place_if_new_config_is_invalid(self):
        old_configuration = deepcopy(self.runner._configuration)

        self.runner._yaml_path = path_to_invalid_config
        self.runner.reload_configuration()

        assert self.runner._configuration == old_configuration

    def test_reload_configuration_logs_error_when_new_configuration_is_invalid(self):
        self.runner._yaml_path = path_to_invalid_config

        with AssertEmitsLogMessage(
            self.handler,
            ERROR,
            prefix="Invalid configuration, leaving old configuration in place: ",
        ):
            self.runner.reload_configuration()

    def test_reload_configuration_creates_new_logprep_instances_with_new_configuration(self):
        self.runner._manager.set_count(3)
        old_logprep_instances = list(self.runner._manager._pipelines)

        self.runner.reload_configuration()

        assert set(old_logprep_instances).isdisjoint(set(self.runner._manager._pipelines))
        assert len(self.runner._manager._pipelines) == 3

    def get_path(self, filename):
        return join(split(__path__), filename)
