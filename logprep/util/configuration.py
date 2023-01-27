"""This module is used to create the configuration for the runner."""

import re
import sys
from logging import Logger
from typing import List

from ruamel.yaml.scanner import ScannerError
from colorama import Fore

from logprep.factory import Factory
from logprep.factory_error import FactoryError
from logprep.factory_error import (
    UnknownComponentTypeError,
    InvalidConfigurationError as FactoryInvalidConfigurationError,
)
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.util.getter import GetterFactory
from logprep.util.helper import print_fcolor


class InvalidConfigurationError(BaseException):
    """Base class for Configuration related exceptions."""

    def __init__(self, unprefixed_message: str = None, message: str = None):
        if unprefixed_message is not None:
            super().__init__(unprefixed_message)
        elif message is not None:
            super().__init__(f"Invalid Configuration: {message}")
        else:
            super().__init__("Invalid Configuration.")


class InvalidConfigurationErrors(InvalidConfigurationError):
    """Raise for multiple Configuration related exceptions."""

    def __init__(self, errors: List[InvalidConfigurationError]):
        self.errors = errors
        super().__init__("\n".join([str(error) for error in self.errors]))


class RequiredConfigurationKeyMissingError(InvalidConfigurationError):
    """Raise if required option is missing in configuration."""

    def __init__(self, key: str):
        super().__init__(f"Required option is missing: {key}")


class InvalidLabelingSchemaError(InvalidConfigurationError):
    """Raise if labeling schema is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid labeling schema: {message}")


class InvalidRulesError(InvalidConfigurationError):
    """Raise if set of rules is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid rule set: {message}")


class InvalidProcessorConfigurationError(InvalidConfigurationError):
    """Raise if processor configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid processor configuration: {message}")


class InvalidConnectorConfigurationError(InvalidConfigurationError):
    """Raise if connector configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid connector configuration: {message}")


class InvalidInputConnectorConfigurationError(InvalidConfigurationError):
    """Raise if input connector configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid input connector configuration: {message}")


class InvalidOutputConnectorConfigurationError(InvalidConfigurationError):
    """Raise if output connector configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid output connector configuration: {message}")


class IncalidMetricsConfigurationError(InvalidConfigurationError):
    """Raise if status_logger configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid metrics configuration: {message}")


class Configuration(dict):
    """Used to create and verify a configuration dict parsed from a YAML file."""

    path: str

    @staticmethod
    def create_from_yaml(path: str) -> "Configuration":
        """Create configuration from a YAML file.

        Parameters
        ----------
        path : str
            Path of file to create configuration from.

        Returns
        -------
        config : Configuration
            Configuration object based on dictionary.

        """
        config_getter = GetterFactory.from_string(path)
        try:
            configuration = config_getter.get_json()
        except ValueError:
            try:
                configuration = config_getter.get_yaml()
            except ScannerError as error:
                print_fcolor(Fore.RED, f"Error parsing YAML file: {path}\n{error}")
                sys.exit(1)
        config = Configuration()
        config.path = f"{config_getter.protocol}://{config_getter.target}"
        config.update(configuration)

        return config

    def verify(self, logger: Logger):
        """Verify the configuration."""
        errors = self._perform_verfification_and_get_errors(logger)
        self._print_errors(errors)

        for error in errors:
            raise error

    def verify_pipeline_only(self, logger: Logger):
        """Verify the configuration only for the pipeline.

        This is used to check rules where it is not necessary to start the whole framework.
        """
        errors = []
        try:
            self._verify_pipeline(logger, ignore_rule_errors=False)
        except InvalidConfigurationError as error:
            errors.append(error)
        self._print_errors(errors)

        for error in errors:
            raise error

    def _perform_verfification_and_get_errors(
        self, logger: Logger
    ) -> List[InvalidConfigurationError]:
        errors = []
        try:
            self._verify_required_keys_exist()
        except InvalidConfigurationError as error:
            errors.append(error)
        try:
            self._verify_values_make_sense()
        except InvalidConfigurationError as error:
            errors.append(error)
        try:
            self._verify_input(logger)
        except InvalidConfigurationError as error:
            errors.append(error)
        try:
            self._verify_output(logger)
        except InvalidConfigurationError as error:
            errors.append(error)
        try:
            self._verify_pipeline(logger)
        except InvalidConfigurationError as error:
            errors.append(error)
        if self.get("metrics", {}):
            try:
                self._verify_metrics_config()
            except InvalidConfigurationError as error:
                errors.append(error)
        return errors

    def _verify_required_keys_exist(self):
        required_keys = ["process_count", "timeout"]

        errors = []
        for key in required_keys:
            if key not in self:
                errors.append(RequiredConfigurationKeyMissingError(key))
        if errors:
            raise InvalidConfigurationErrors(errors)

    def _verify_values_make_sense(self):
        errors = []
        if "process_count" in self and self["process_count"] < 1:
            errors.append(
                InvalidConfigurationError(
                    message=f"Process count must be an integer of one or larger, not: "
                    f'{self["process_count"]}'
                )
            )
        if "pipeline" in self and not self["pipeline"]:
            errors.append(
                InvalidConfigurationError(message='"pipeline" must contain at least one item!')
            )

        if errors:
            raise InvalidConfigurationErrors(errors)

    def _verify_input(self, logger):
        try:
            _ = Factory.create(self["input"], logger)
        except FactoryError as error:
            raise InvalidInputConnectorConfigurationError(str(error)) from error
        except TypeError as error:
            msg = self._format_type_error(error)
            raise InvalidInputConnectorConfigurationError(msg) from error
        except KeyError as error:
            raise RequiredConfigurationKeyMissingError("input") from error

    def _verify_output(self, logger):
        try:
            _ = Factory.create(self["output"], logger)
        except FactoryError as error:
            raise InvalidOutputConnectorConfigurationError(str(error)) from error
        except TypeError as error:
            msg = self._format_type_error(error)
            raise InvalidOutputConnectorConfigurationError(msg) from error
        except KeyError as error:
            raise RequiredConfigurationKeyMissingError("output") from error

    @staticmethod
    def _format_type_error(error: TypeError) -> str:
        msg = str(error)
        if "missing" in str(error):
            parameters = re.split(r"argument(s)?:", str(error))[-1].strip()
            msg = f"Required option(s) are missing: {parameters}."
        elif "unexpected" in str(error):
            parameter = str(error).rsplit("argument ", maxsplit=1)[-1].strip()
            msg = f"Unknown option: {parameter}."
        return msg

    def _verify_pipeline(self, logger: Logger, ignore_rule_errors=False):
        if not self.get("pipeline"):
            raise RequiredConfigurationKeyMissingError("pipeline")

        if not isinstance(self["pipeline"], list):
            error = InvalidConfigurationError(
                '"pipeline" must be a list of processor dictionary configurations!'
            )
            raise InvalidConfigurationErrors([error])

        errors = []
        for processor_config in self["pipeline"]:
            try:
                Factory.create(processor_config, logger)
            except (FactoryInvalidConfigurationError, UnknownComponentTypeError) as error:
                errors.append(
                    InvalidProcessorConfigurationError(
                        f"{list(processor_config.keys())[0]} - {error}"
                    )
                )
            except TypeError as error:
                msg = self._format_type_error(error)
                errors.append(
                    InvalidProcessorConfigurationError(
                        f"{list(processor_config.keys())[0]} - {msg}"
                    )
                )
            except InvalidRuleDefinitionError:
                if not ignore_rule_errors:
                    errors.append(
                        InvalidConfigurationError(
                            "Could not verify configuration for processor instance "
                            f"'{list(processor_config.keys())[0]}', because it has invalid rules."
                        )
                    )
        if errors:
            raise InvalidConfigurationErrors(errors)

    def _verify_metrics_config(self):
        if self.get("metrics"):
            errors = []
            required_keys = [
                "enabled",
                "period",
                "cumulative",
                "aggregate_processes",
                "measure_time",
                "targets",
            ]

            for key in required_keys:
                if key not in self["metrics"]:
                    errors.append(RequiredConfigurationKeyMissingError(f"metrics > {key}"))

            targets = self.get("metrics").get("targets", [])

            if not targets:
                errors.append(
                    IncalidMetricsConfigurationError("At least one target has to be configured")
                )

            for target in targets:
                current_target = list(target.keys())[0]
                try:
                    if current_target == "prometheus":
                        self._verify_status_logger_prometheus_target(target["prometheus"])
                    elif current_target == "file":
                        self._verify_status_logger_file_target(target["file"])
                    else:
                        raise IncalidMetricsConfigurationError(f"Unknown target '{current_target}'")
                except InvalidConfigurationError as error:
                    errors.append(error)

            try:
                self._verify_measure_time_config(self.get("metrics").get("measure_time"))
            except InvalidConfigurationError as error:
                errors.append(error)

            if errors:
                raise InvalidConfigurationErrors(errors)

    @staticmethod
    def _verify_status_logger_prometheus_target(target_config):
        if target_config is None or not target_config.get("port"):
            raise RequiredConfigurationKeyMissingError("metrics > targets > prometheus > port")

    @staticmethod
    def _verify_status_logger_file_target(target_config):
        required_keys = {"path", "rollover_interval", "backup_count"}
        given_keys = set(target_config.keys())
        missing_keys = required_keys.difference(given_keys)

        if missing_keys:
            raise RequiredConfigurationKeyMissingError(
                f"The following option keys for the "
                f"metrics file target are missing: "
                f"{missing_keys}"
            )

    @staticmethod
    def _verify_measure_time_config(measure_time_config):
        required_keys = {"enabled", "append_to_event"}
        given_keys = set(measure_time_config.keys())
        missing_keys = required_keys.difference(given_keys)

        if missing_keys:
            raise RequiredConfigurationKeyMissingError(
                f"The following option keys for the "
                f"measure time configs are missing: "
                f"{missing_keys}"
            )

    @staticmethod
    def _print_errors(errors: List[BaseException]):
        for error in errors:
            print_fcolor(Fore.RED, str(error))
