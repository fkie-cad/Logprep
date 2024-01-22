"""This module is used to create the configuration for the runner."""

from copy import deepcopy
from itertools import chain
from typing import Any, List

from attr import define, field, validators
from ruamel.yaml.scanner import ScannerError

from logprep.abc.getter import Getter
from logprep.abc.processor import Processor
from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.util.defaults import DEFAULT_CONFIG_LOCATION
from logprep.util.getter import GetterFactory


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


class MissingEnvironmentError(InvalidConfigurationError):
    """Raise if environment variables are missing"""

    def __init__(self, message: str):
        super().__init__(f"Environment variable(s) used, but not set: {message}")


@define(kw_only=True)
class Configuration:
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

    _configs: tuple["Configuration"] = field(
        validator=validators.instance_of(tuple),
        factory=tuple,
    )

    def _get_last_value(self, attribute: str) -> Any:
        if self._configs:
            values = [
                getattr(self, attribute),
                *[
                    getattr(config, attribute)
                    for config in self._configs
                    if getattr(config, attribute)
                ],
            ]
            return values[-1]
        return getattr(self, attribute)

    @property
    def paths(self) -> list[str]:
        """Paths of the configuration files."""
        # pylint: disable=protected-access
        targets = (
            (config._getter.protocol, config._getter.target)
            for config in self._configs
            if config._getter
        )
        # pylint: enable=protected-access
        return [f"{protocol}://{target}" for protocol, target in targets]

    @property
    def version(self) -> str:
        """Version of the configuration file."""
        return self._get_last_value("_version")

    @version.setter
    def version(self, version: str) -> None:
        """Setter for version."""
        self._version = version

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

    @input.setter
    def input(self, input_config: dict) -> None:
        """Setter for input connector configuration."""
        self._input = input_config

    @property
    def output(self) -> dict:
        """Output connector configuration."""
        return self._get_last_value("_output")

    @output.setter
    def output(self, output: dict) -> None:
        """Setter for Output connector configuration."""
        self._output = output

    @property
    def pipeline(self) -> list[dict]:
        """Pipeline configuration."""
        # pylint: disable=protected-access
        pipelines = (config._pipeline for config in self._configs if config._pipeline)
        # pylint: enable=protected-access
        return list(chain(self._pipeline, *pipelines))

    @pipeline.setter
    def pipeline(self, pipeline: list[dict]) -> None:
        """Pipeline configuration."""
        self._pipeline = pipeline

    @property
    def metrics(self) -> dict:
        """Metrics configuration."""
        return self._get_last_value("_metrics")

    @metrics.setter
    def metrics(self, metrics: dict) -> None:
        """Setter for metrics configuration."""
        self._metrics = metrics

    @classmethod
    def _create_from_source(cls, path: str) -> "Configuration":
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
        return Configuration(**config_dict, getter=config_getter)

    @classmethod
    def create_from_sources(cls, config_paths: list[str]) -> "Configuration":
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
                config = Configuration._create_from_source(config_path)
                configs.append(config)
            except (ValueError, ScannerError, TypeError) as error:
                errors.append(error)
        if errors:
            raise InvalidConfigurationErrors(errors)
        config = Configuration()
        config._configs = tuple(configs)
        return config

    def verify(self):
        """Verify the configuration."""
        errors = []
        try:
            self._verify_environment()
        except MissingEnvironmentError as error:
            errors.append(error)
        try:
            if not self.input:
                raise RequiredConfigurationKeyMissingError("input")
            Factory.create(self.input)
        except Exception as error:  # pylint: disable=broad-except
            errors.append(error)
        if not self.output:
            errors.append(RequiredConfigurationKeyMissingError("output"))
        else:
            for output_name, output_config in self.output.items():
                try:
                    Factory.create({output_name: output_config})
                except Exception as error:  # pylint: disable=broad-except
                    errors.append(error)
        for processor_config in self.pipeline:
            try:
                processor = Factory.create(processor_config)
                self._verify_processor_outputs(processor_config)
                self._verify_rules(processor)
            except Exception as error:  # pylint: disable=broad-except
                errors.append(error)
        try:
            self._verify_metrics_config()
        except Exception as error:  # pylint: disable=broad-except
            errors.append(error)
        if errors:
            raise InvalidConfigurationErrors(errors)

    def _verify_processor_outputs(self, processor_config):
        processor_config = deepcopy(processor_config)
        processor_name, processor_config = processor_config.popitem()
        if "outputs" not in processor_config:
            return
        outputs = processor_config.get("outputs")
        for output in outputs:
            for output_name, _ in output.items():
                if output_name not in self.output:
                    raise InvalidProcessorConfigurationError(
                        f"{processor_name}: output '{output_name}' does not exist in logprep outputs"  # pylint: disable=line-too-long
                    )

    def _verify_environment(self):
        # pylint: disable=protected-access
        getters = (config._getter for config in self._configs if config._getter)
        # pylint: enable=protected-access
        missing_env_vars = tuple(chain(*[getter.missing_env_vars for getter in getters]))
        if missing_env_vars:
            missing_env_error = MissingEnvironmentError(", ".join(missing_env_vars))
            raise InvalidConfigurationErrors([missing_env_error])

    def _verify_rules(self, processor: Processor) -> None:
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

    def _verify_outputs(self, processor: Processor, rule) -> None:
        for output in rule.outputs:
            for output_name, _ in output.items():
                if output_name not in self["output"]:
                    raise InvalidRuleDefinitionError(
                        f"{processor.describe()}: output"
                        f" '{output_name}' does not exist in logprep outputs"
                    )

    def _verify_metrics_config(self):
        errors = []
        for key in self.metrics:
            if key not in ["enabled", "port"]:
                errors.append(InvalidConfigurationError(f"Unknown metrics option: {key}"))
        if "enabled" not in self.metrics:
            errors.append(RequiredConfigurationKeyMissingError("metrics > enabled"))
        if errors:
            raise InvalidConfigurationErrors(errors)
