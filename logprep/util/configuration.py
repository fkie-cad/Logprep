"""This module is used to create the configuration for the runner."""

import json
from copy import deepcopy
from itertools import chain
from typing import Any, List

from attr import define, field, validators
from attrs import asdict
from ruamel.yaml import YAML
from ruamel.yaml.compat import StringIO
from ruamel.yaml.scanner import ScannerError

from logprep.abc.getter import Getter
from logprep.abc.processor import Processor
from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.util.defaults import DEFAULT_CONFIG_LOCATION
from logprep.util.getter import GetterFactory


class MyYAML(YAML):
    def dump(self, data, stream=None, **kw):
        inefficient = False
        if stream is None:
            inefficient = True
            stream = StringIO()
        YAML.dump(self, data, stream, **kw)
        if inefficient:
            return stream.getvalue()


yaml = MyYAML(typ="unsafe", pure=True)


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
    version: str = field(validator=validators.instance_of(str), converter=str, default="unset")
    """Version of the configuration file. Defaults to `unset`."""
    config_refresh_interval: int = field(validator=validators.instance_of(int), default=0)
    """Interval in seconds to refresh the configuration. Defaults to `0`."""
    process_count: int = field(validator=[validators.instance_of(int), validators.ge(1)], default=1)
    """Number of logprep processes to start. Defaults to `1`."""
    timeout: float = field(validator=[validators.instance_of(float), validators.gt(0)], default=5.0)
    """Timeout in seconds for each logprep process. Defaults to `5.0`."""
    logger: dict = field(validator=validators.instance_of(dict), default={"level": "INFO"})
    """Logger configuration. Defaults to `{"level": "INFO"}`."""
    input: dict = field(validator=validators.instance_of(dict), factory=dict)
    """Input connector configuration. Defaults to `{}`."""
    output: dict = field(validator=validators.instance_of(dict), factory=dict)
    """Output connector configuration. Defaults to `{}`."""
    pipeline: list[dict] = field(validator=validators.instance_of(list), factory=list)
    """Pipeline configuration. Defaults to `[]`."""
    metrics: dict = field(
        validator=validators.instance_of(dict), default={"enabled": False, "port": 8000}
    )
    """Metrics configuration. Defaults to `{"enabled": False, "port": 8000}`."""

    _getter: Getter = field(
        validator=validators.instance_of(Getter),
        default=GetterFactory.from_string(DEFAULT_CONFIG_LOCATION),
        repr=False,
    )

    _configs: tuple["Configuration"] = field(
        validator=validators.instance_of(tuple),
        factory=tuple,
        repr=False,
    )

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

    @classmethod
    def from_source(cls, path: str) -> "Configuration":
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
            try:
                config_dict = config_getter.get_json()
            except ValueError:
                config_dict = config_getter.get_yaml()
            config = Configuration(**config_dict, getter=config_getter)
        except (ScannerError, ValueError, TypeError) as error:
            raise InvalidConfigurationError(f"Invalid configuration file: {path}") from error
        config._configs = (config,)
        return config

    @classmethod
    def from_sources(cls, config_paths: list[str]) -> "Configuration":
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
                config = Configuration.from_source(config_path)
                configs.append(config)
            except InvalidConfigurationError as error:
                errors.append(error)
        if errors:
            raise InvalidConfigurationErrors(errors)
        configuration = Configuration()
        configuration._configs = tuple(configs)
        cls._set_attributes_from_configs(configuration)
        return configuration

    def as_dict(self) -> dict:
        """Return the configuration as dict."""
        return asdict(
            self, filter=lambda attribute, _: attribute.name not in ("_getter", "_configs")
        )

    def as_json(self, indent=None) -> str:
        """Return the configuration as json string."""
        return json.dumps(self.as_dict(), indent=indent)

    def as_yaml(self) -> str:
        """Return the configuration as yaml string."""
        return yaml.dump(self.as_dict())

    def reload(self) -> None:
        """Reload the configuration."""
        new_config = Configuration.from_sources(self.paths)
        if new_config.version == self.version:
            raise InvalidConfigurationError("Configuration version has not changed")
        new_config.verify()
        self._configs = new_config._configs  # pylint: disable=protected-access
        self._set_attributes_from_configs()

    def _set_attributes_from_configs(self) -> None:
        for attribute in filter(lambda x: x.repr, self.__attrs_attrs__):
            setattr(
                self,
                attribute.name,
                self._get_last_value(self._configs, attribute.name),
            )
        pipelines = (config.pipeline for config in self._configs if config.pipeline)
        self.pipeline = list(chain(*pipelines))

    @staticmethod
    def _get_last_value(configs: list["Configuration"], attribute: str) -> Any:
        if configs:
            values = [getattr(config, attribute) for config in configs]
            return values[-1]
        return None

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
