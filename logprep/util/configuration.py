"""This module is used to create the configuration for the runner."""

import re
import sys
from copy import deepcopy
from functools import reduce
from itertools import chain
from logging import Logger
from pathlib import Path
from typing import List

from attr import define, field, validators
from colorama import Fore
from ruamel.yaml.scanner import ScannerError

from logprep.abc.getter import Getter
from logprep.abc.processor import Processor
from logprep.factory import Factory
from logprep.factory_error import FactoryError
from logprep.factory_error import (
    InvalidConfigurationError as FactoryInvalidConfigurationError,
)
from logprep.factory_error import UnknownComponentTypeError
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.util.defaults import DEFAULT_CONFIG_LOCATION
from logprep.util.getter import GetterFactory
from logprep.util.helper import print_fcolor
from logprep.util.json_handling import dump_config_as_file


class InvalidConfigurationError(Exception):
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


class InvalidProcessorConfigurationError(InvalidConfigurationError):
    """Raise if processor configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid processor configuration: {message}")


class InvalidInputConnectorConfigurationError(InvalidConfigurationError):
    """Raise if input connector configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid input connector configuration: {message}")


class InvalidOutputConnectorConfigurationError(InvalidConfigurationError):
    """Raise if output connector configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(f"Invalid output connector configuration: {message}")


class MissingEnvironmentError(InvalidConfigurationError):
    """Raise if environment variables are missing"""

    def __init__(self, message: str):
        super().__init__(f"Environment variable(s) used, but not set: {message}")


@define(kw_only=True)
class NewConfiguration:
    _version: str = field(validator=validators.instance_of(str), converter=str, default="undefined")
    """Version of the configuration file. Defaults to `undefined`."""
    _process_count: int = field(
        validator=[validators.instance_of(int), validators.ge(1)], default=1
    )
    """Number of logprep processes to start. Defaults to `1`."""
    _timeout: float = field(
        validator=[validators.instance_of(float), validators.gt(0)], default=5.0
    )
    """Timeout in seconds for each logprep process. Defaults to `5.0`."""
    _logger: dict = field(validator=validators.instance_of(dict), default={"level": "INFO"})
    """Logger configuration. Defaults to `{"level": "INFO"}`."""
    _input: dict = field(validator=validators.instance_of(dict), factory=dict)
    """Input connector configuration. Defaults to `{}`."""
    _output: dict = field(validator=validators.instance_of(dict), factory=dict)
    """Output connector configuration. Defaults to `{}`."""
    _pipeline: list[dict] = field(validator=validators.instance_of(list), factory=list)
    """Pipeline configuration. Defaults to `[]`."""
    _metrics: dict = field(
        validator=validators.instance_of(dict), default={"enabled": False, "port": 8000}
    )
    """Metrics configuration. Defaults to `{"enabled": False, "port": 8000}`."""

    _getter: Getter = field(
        validator=validators.instance_of(Getter),
        default=GetterFactory.from_string(DEFAULT_CONFIG_LOCATION),
    )

    _configs: tuple["NewConfiguration"] = field(
        validator=validators.instance_of(tuple),
        factory=tuple,
    )

    def _get_last_value(self, attribute: str) -> property:
        if self._configs:
            values = [
                getattr(config, attribute) for config in self._configs if getattr(config, attribute)
            ]
            return values[-1]
        return getattr(self, attribute)

    @property
    def version(self) -> str:
        """Version of the configuration file."""
        return self._get_last_value("_version")

    @property
    def process_count(self) -> int:
        """Number of logprep processes to start."""
        return self._get_last_value("_process_count")

    @property
    def timeout(self) -> float:
        """Timeout in seconds for each logprep process."""
        return self._get_last_value("_timeout")

    @property
    def logger(self) -> dict:
        """Logger configuration."""
        return self._get_last_value("_logger")

    @property
    def input(self) -> dict:
        """Input connector configuration."""
        return self._get_last_value("_input")

    @property
    def output(self) -> dict:
        """Output connector configuration."""
        return self._get_last_value("_output")

    @property
    def pipeline(self) -> list[dict]:
        """Pipeline configuration."""
        # pylint: disable=protected-access
        pipelines = (config._pipeline for config in self._configs if config._pipeline)
        # pylint: enable=protected-access
        return list(chain(*pipelines))

    @property
    def metrics(self) -> dict:
        """Metrics configuration."""
        return self._get_last_value("_metrics")

    @classmethod
    def _create_from_source(cls, path: str) -> "NewConfiguration":
        """Create configuration from an uri source.

        Parameters
        ----------
        path : str
            uri of file to create configuration from.

        Returns
        -------
        config : Configuration
            Configuration object attrs class.

        """
        config_getter = GetterFactory.from_string(path)
        try:
            config_dict = config_getter.get_json()
        except ValueError:
            config_dict = config_getter.get_yaml()
        return NewConfiguration(**config_dict, getter=config_getter)

    @classmethod
    def create_from_sources(cls, config_paths: list[str]) -> "NewConfiguration":
        """Creates configuration from a list of configuration sources.

        Parameters
        ----------
        paths : list[str]
            List of configuration sources (URI) to create configuration from.

        Returns
        -------
        config : Configuration
            resulting configuration object.

        """
        errors = []
        configs = []
        for config_path in config_paths:
            try:
                config = NewConfiguration._create_from_source(config_path)
                configs.append(config)
            except (ValueError, ScannerError, TypeError) as error:
                errors.append(error)
        if errors:
            raise InvalidConfigurationErrors(errors)
        config = NewConfiguration()
        config._configs = tuple(configs)
        return config

    def verify(self):
        """Verify the configuration."""
        errors = []
        try:
            Factory.create(self.input)
        except Exception as error:  # pylint: disable=broad-except
            errors.append(error)
        for output_name, output_config in self.output.items():
            try:
                Factory.create({output_name: output_config})
            except Exception as error:  # pylint: disable=broad-except
                errors.append(error)
        for processor_config in self.pipeline:
            try:
                Factory.create(processor_config)
            except Exception as error:  # pylint: disable=broad-except
                errors.append(error)
        if errors:
            raise InvalidConfigurationErrors(errors)


class Configuration(dict):
    """Used to create and verify a configuration dict parsed from a YAML file."""

    getters: list[Getter]

    @property
    def paths(self) -> list[str]:
        """returns the path of the configuration"""
        return [f"{getter.protocol}://{getter.target}" for getter in self.getters]

    @paths.setter
    def paths(self, paths: list[str]) -> None:
        """sets the path and getter"""
        self.getters = [GetterFactory.from_string(path) for path in paths]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.getters = []

    @classmethod
    def create_from_yaml(cls, path: str) -> "Configuration":
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
            config_dict = config_getter.get_json()
        except ValueError:
            try:
                config_dict = config_getter.get_yaml()
            except ScannerError as error:
                print_fcolor(Fore.RED, f"Error parsing YAML file: {path}\n{error}")
                sys.exit(1)
        config = Configuration()
        config.getters.append(config_getter)
        config.update(config_dict)
        return config

    @classmethod
    def create_from_yamls(cls, paths: list[str]) -> "Configuration":
        """Create configuration from a list of YAML files.

        Parameters
        ----------
        paths : list[str]
            List of paths of files to create configuration from.

        Returns
        -------
        config : Configuration
            Configuration object based on dictionary.

        """
        configs = (Configuration.create_from_yaml(config) for config in paths)
        merged_config = Configuration(reduce(lambda x, y: x | y, configs))
        merged_config.getters = [getter for config in configs for getter in config.getters]
        return merged_config

    @staticmethod
    def patch_yaml_with_json_connectors(
        original_config_path: str, output_dir: str, input_file_path: str = None
    ) -> str:
        """
        Patches a given configuration file with jsonl input and output connectors, while
        maintaining the input preprocessors. Additionally, the process_count is set to one and the
        metrics configuration are removed, if present.

        Parameters
        ----------
        original_config_path : str
            Path to the original configuration file that should be patched
        output_dir : str
            Path where the patched configuration file should be saved to. That is the same
            path where the jsonl connectors read and write the input/output files.
        input_file_path : Optional[str]
            If a concrete input file is given, then it is used in the patched input connector

        Returns
        -------
        patched_config_path : str
            The path to the patched configuration file
        """
        configuration = GetterFactory.from_string(original_config_path).get_yaml()
        configured_input = configuration.get("input", {})
        input_file_path = input_file_path if input_file_path else f"{output_dir}/input.json"
        input_type = "jsonl_input" if input_file_path.endswith(".jsonl") else "json_input"
        configuration["input"] = {
            "patched_input": {
                "type": input_type,
                "documents_path": input_file_path,
            }
        }
        if configured_input:
            input_name = list(configured_input.keys())[0]
            preprocessors = configured_input.get(input_name, {}).get("preprocessing", {})
            if preprocessors:
                configuration["input"]["patched_input"]["preprocessing"] = preprocessors
        configuration["output"] = {
            "patched_output": {
                "type": "jsonl_output",
                "output_file": f"{output_dir}/output.json",
                "output_file_custom": f"{output_dir}/output_custom.json",
                "output_file_error": f"{output_dir}/output_error.json",
            }
        }
        configuration["process_count"] = 1
        if "metrics" in configuration:
            del configuration["metrics"]
        patched_config_path = Path(output_dir) / "patched_config.yml"
        dump_config_as_file(str(patched_config_path), configuration)
        return str(patched_config_path)

    def verify(self, logger: Logger):
        """Verify the configuration."""
        errors = self._check_for_errors(logger)
        self._print_and_raise_errors(errors)
        for error in errors:
            raise error

    def verify_pipeline_only(self, logger: Logger):
        """Verify the configuration only for the pipeline.

        This is used to check rules where it is not necessary to start the whole framework.
        """
        errors = []
        try:
            self._verify_pipeline(logger)
        except InvalidConfigurationError as error:
            errors.append(error)
        self._print_and_raise_errors(errors)

    def verify_pipeline_without_processor_outputs(self, logger: Logger):
        """Verify the configuration only for the pipeline, but ignore processor output errors.
        This is used to check if the configuration is valid inside the auto rule tester and the
        rule corpus tester, as the configuration does not have an output there.
        """
        errors = []
        try:
            self._verify_pipeline_without_processor_outputs(logger)
        except InvalidConfigurationError as error:
            errors.append(error)
        self._print_and_raise_errors(errors)

    def _check_for_errors(self, logger: Logger) -> List[InvalidConfigurationError]:
        errors = []
        try:
            self._verify_environment()
        except MissingEnvironmentError as error:
            errors.append(error)
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

    def _verify_environment(self):
        missing_env_vars = tuple(chain(*[getter.missing_env_vars for getter in self.getters]))
        if missing_env_vars:
            missing_env_error = MissingEnvironmentError(", ".join(missing_env_vars))
            raise InvalidConfigurationErrors([missing_env_error])

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
            output_configs = self.get("output")
            output_names = list(output_configs.keys())
            for output_name in output_names:
                output_config = output_configs.get(output_name)
                Factory.create({output_name: output_config}, logger)
        except FactoryError as error:
            raise InvalidOutputConnectorConfigurationError(str(error)) from error
        except TypeError as error:
            msg = self._format_type_error(error)
            raise InvalidOutputConnectorConfigurationError(msg) from error
        except (AttributeError, KeyError) as error:
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

    def _verify_pipeline(self, logger: Logger):
        self._verify_pipeline_key()
        errors = []
        for processor_config in self["pipeline"]:
            processor = self._verify_processor(errors, logger, processor_config)
            try:
                self._verify_rules(processor)
            except InvalidRuleDefinitionError as error:
                errors.append(error)
            try:
                self._verify_processor_outputs(processor_config)
            except InvalidProcessorConfigurationError as error:
                errors.append(error)
        if errors:
            raise InvalidConfigurationErrors(errors)

    def _verify_pipeline_without_processor_outputs(self, logger: Logger):
        self._verify_pipeline_key()
        errors = []
        for processor_config in self["pipeline"]:
            self._verify_processor(errors, logger, processor_config)
        if errors:
            raise InvalidConfigurationErrors(errors)

    def _verify_pipeline_key(self):
        if not self.get("pipeline"):
            raise RequiredConfigurationKeyMissingError("pipeline")
        if not isinstance(self["pipeline"], list):
            error = InvalidConfigurationError(
                '"pipeline" must be a list of processor dictionary configurations!'
            )
            raise InvalidConfigurationErrors([error])

    def _verify_processor(self, errors, logger, processor_config):
        processor = None
        try:
            processor = Factory.create(processor_config, logger)
        except (FactoryInvalidConfigurationError, UnknownComponentTypeError) as error:
            errors.append(
                InvalidProcessorConfigurationError(f"{list(processor_config.keys())[0]} - {error}")
            )
        except TypeError as error:
            msg = self._format_type_error(error)
            errors.append(
                InvalidProcessorConfigurationError(f"{list(processor_config.keys())[0]} - {msg}")
            )
        except InvalidRuleDefinitionError:
            errors.append(
                InvalidConfigurationError(
                    "Could not verify configuration for processor instance "
                    f"'{list(processor_config.keys())[0]}', because it has invalid rules."
                )
            )
        return processor

    def _verify_rules(self, processor: Processor):
        if not processor:
            return
        rule_ids = []
        for rule in processor.rules:
            if rule.id in rule_ids:
                raise InvalidRuleDefinitionError(f"Duplicate rule id: {rule.id}, {rule}")
            rule_ids.append(rule.id)
            if not hasattr(processor.rule_class, "outputs"):
                continue
            self._verify_outputs(processor, rule)
        duplicates = [item for item in rule_ids if rule_ids.count(item) > 1]
        if duplicates:
            raise InvalidRuleDefinitionError(f"Duplicate rule ids: {duplicates}")

    def _verify_outputs(self, processor, rule):
        for output in rule.outputs:
            for output_name, _ in output.items():
                if output_name not in self["output"]:
                    raise InvalidRuleDefinitionError(
                        f"{processor.describe()}: output"
                        f" '{output_name}' does not exist in logprep outputs"
                    )

    def _verify_processor_outputs(self, processor_config):
        processor_config = deepcopy(processor_config)
        processor_name, processor_config = processor_config.popitem()
        if "outputs" not in processor_config:
            return
        if "output" not in self:
            return
        outputs = processor_config.get("outputs")
        for output in outputs:
            for output_name, _ in output.items():
                if output_name not in self["output"]:
                    raise InvalidProcessorConfigurationError(
                        f"{processor_name}: output '{output_name}' does not exist in logprep outputs"
                    )

    def _verify_metrics_config(self):
        metrics_config = self.get("metrics")
        if metrics_config:
            errors = []
            if "enabled" not in metrics_config:
                errors.append(RequiredConfigurationKeyMissingError("metrics > enabled"))
            if errors:
                raise InvalidConfigurationErrors(errors)

    @staticmethod
    def _print_and_raise_errors(errors: List[BaseException]):
        for error in errors:
            print_fcolor(Fore.RED, str(error))
        for error in errors:
            raise error
