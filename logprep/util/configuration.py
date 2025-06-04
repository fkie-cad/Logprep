"""
Configuration is done via YAML or JSON files or http api resources.
Logprep searches for the file :code:`/etc/logprep/pipeline.yml` if no
configuration file is passed.

You can pass multiple configuration files via valid file paths or urls.

..  code-block:: bash
    :caption: Valid Run Examples

    logprep run /different/path/file.yml
    logprep run http://url-to-our-yaml-file-or-api
    logprep run http://api/v1/pipeline http://api/v1/addition_processor_pipline /path/to/connector.yaml


.. security-best-practice::
   :title: Configuration - Combining multiple configuration files

   Consider when using multiple configuration files logprep will reject all configuration files
   if one can not be retrieved or is not valid.
   If using multiple files ensure that all can be loaded safely and that all endpoints (if using
   http resources) are accessible.

Configuration File Structure
----------------------------

..  code-block:: yaml
    :caption: Example of a complete configuration file

    version: config-1.0
    process_count: 2
    restart_count: 5
    timeout: 5
    logger:
        level: INFO
    input:
        kafka:
            type: confluentkafka_input
            topic: consumer
            offset_reset_policy: smallest
            kafka_config:
                bootstrap.servers: localhost:9092
                group.id: test
    output:
        kafka:
            type: confluentkafka_output
            topic: producer
            flush_timeout: 30
            send_timeout: 2
            kafka_config:
                bootstrap.servers: localhost:9092
    pipeline:
    - labelername:
        type: labeler
        schema: examples/exampledata/rules/labeler/schema.json
        include_parent_labels: true
        rules:
            - examples/exampledata/rules/labeler/rules

    - dissectorname:
        type: dissector
        rules:
            - examples/exampledata/rules/dissector/rules

    - dropper:
        type: dropper
        rules:
            - examples/exampledata/rules/dropper/rules
            - filter: "test_dropper"
            dropper:
                drop:
                - drop_me
            description: "..."

    - pre_detector:
        type: pre_detector
        rules:
            - examples/exampledata/rules/pre_detector/rules
        outputs:
            - opensearch: sre
        tree_config: examples/exampledata/rules/pre_detector/tree_config.json
        alert_ip_list_path: examples/exampledata/rules/pre_detector/alert_ips.yml

    - amides:
        type: amides
        rules:
            - examples/exampledata/rules/amides/rules
        models_path: examples/exampledata/models/model.zip
        num_rule_attributions: 10
        max_cache_entries: 1000000
        decision_threshold: 0.32

    - pseudonymizer:
        type: pseudonymizer
        pubkey_analyst: examples/exampledata/rules/pseudonymizer/example_analyst_pub.pem
        pubkey_depseudo: examples/exampledata/rules/pseudonymizer/example_depseudo_pub.pem
        regex_mapping: examples/exampledata/rules/pseudonymizer/regex_mapping.yml
        hash_salt: a_secret_tasty_ingredient
        outputs:
            - opensearch: pseudonyms
        rules:
            - examples/exampledata/rules/pseudonymizer/rules
        max_cached_pseudonyms: 1000000

    - calculator:
        type: calculator
        rules:
            - filter: "test_label: execute"
            calculator:
                target_field: "calculation"
                calc: "1 + 1"


The options under :code:`input`, :code:`output` and :code:`pipeline` are passed
to factories in Logprep.
They contain settings for each separate processor and connector.
Details for configuring connectors are described in
:ref:`output` and :ref:`input` and for processors in :ref:`processors`.

It is possible to use environment variables in all configuration
and rule files in all places.
Environment variables have to be set in uppercase and prefixed
with :code:`LOGPREP_`, :code:`GITHUB_`, :code:`PYTEST_` or
:code:`CI_`. Lowercase variables are ignored. Forbidden
variable names are: :code:`["LOGPREP_LIST"]`, as it is already used internally.

.. security-best-practice::
   :title: Configuration Environment Variables

   As it is possible to replace all configuration options with environment variables it is
   recommended to use these especially for sensitive information like usernames, password, secrets
   or hash salts.
   Examples where this could be useful would be the :code:`key` for the hmac calculation (see
   `input` > `preprocessing`) or the :code:`user`/:code:`secret` for the opensearch
   connectors.

The following config file will be valid by setting the given environment variables:

..  code-block:: yaml
    :caption: pipeline.yml config file with environment variables

    version: $LOGPREP_VERSION
    process_count: $LOGPREP_PROCESS_COUNT
    timeout: 0.1
    logger:
        level: $LOGPREP_LOG_LEVEL
    $LOGPREP_PIPELINE
    $LOGPREP_INPUT
    $LOGPREP_OUTPUT


.. code-block:: bash
    :caption: setting the bash environment variables

    export LOGPREP_VERSION="1"
    export LOGPREP_PROCESS_COUNT="1"
    export LOGPREP_LOG_LEVEL="DEBUG"
    export LOGPREP_PIPELINE="
    pipeline:
        - labelername:
            type: labeler
            schema: examples/exampledata/rules/labeler/schema.json
            include_parent_labels: true
            rules:
                - examples/exampledata/rules/labeler/rules"
    export LOGPREP_OUTPUT="
    output:
        kafka:
            type: confluentkafka_output
            topic: producer
            flush_timeout: 30
            send_timeout: 2
            kafka_config:
                bootstrap.servers: localhost:9092"
    export LOGPREP_INPUT="
    input:
        kafka:
            type: confluentkafka_input
            topic: consumer
            offset_reset_policy: smallest
            kafka_config:
                bootstrap.servers: localhost:9092
                group.id: test"
"""

import json
import logging
import os
from copy import deepcopy
from importlib.metadata import version
from itertools import chain
from logging.config import dictConfig
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from attrs import asdict, define, field, fields, validators
from requests import RequestException
from ruamel.yaml import YAML
from ruamel.yaml.compat import StringIO
from ruamel.yaml.scanner import ScannerError
from schedule import Scheduler

from logprep.abc.component import Component
from logprep.abc.getter import Getter
from logprep.abc.processor import Processor
from logprep.factory import Factory
from logprep.factory_error import FactoryError, InvalidConfigurationError
from logprep.metrics.metrics import CounterMetric, GaugeMetric
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.util import http
from logprep.util.credentials import CredentialsEnvNotFoundError, CredentialsFactory
from logprep.util.defaults import (
    DEFAULT_CONFIG_LOCATION,
    DEFAULT_LOG_CONFIG,
    DEFAULT_MESSAGE_BACKLOG_SIZE,
    DEFAULT_RESTART_COUNT,
    ENV_NAME_LOGPREP_CREDENTIALS_FILE,
    MIN_CONFIG_REFRESH_INTERVAL,
)
from logprep.util.getter import GetterFactory, GetterNotFoundError
from logprep.util.rule_loader import RuleLoader

logger = logging.getLogger("Config")


class MyYAML(YAML):
    """helper class to dump yaml with ruamel.yaml"""

    def dump(self, data: Any, stream: Any | None = None, **kw: Any) -> Any:
        inefficient = False
        if stream is None:
            inefficient = True
            stream = StringIO()
        YAML.dump(self, data, stream, **kw)
        if inefficient:
            return stream.getvalue()


yaml = MyYAML(pure=True)


class InvalidConfigurationErrors(InvalidConfigurationError):
    """Raise for multiple Configuration related exceptions."""

    errors: List[InvalidConfigurationError]

    def __init__(self, errors: List[Exception]) -> None:
        unique_errors = []
        for error in errors:
            if not isinstance(error, InvalidConfigurationError):
                error = InvalidConfigurationError(*error.args)
                if error not in unique_errors:
                    unique_errors.append(error)
            else:
                if error not in unique_errors:
                    unique_errors.append(error)
        self.errors = unique_errors
        super().__init__("\n".join([str(error) for error in self.errors]))


class ConfigVersionDidNotChangeError(InvalidConfigurationError):
    """Raise if configuration version did not change."""

    def __init__(self) -> None:
        super().__init__(
            "Configuration version didn't change. Continue running with current version."
        )


class ConfigGetterException(InvalidConfigurationError):
    """Raise if configuration getter fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class RequiredConfigurationKeyMissingError(InvalidConfigurationError):
    """Raise if required option is missing in configuration."""

    def __init__(self, key: str) -> None:
        super().__init__(f"Required option is missing: {key}")


class InvalidProcessorConfigurationError(InvalidConfigurationError):
    """Raise if processor configuration is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(f"Invalid processor configuration: {message}")


class MissingEnvironmentError(InvalidConfigurationError):
    """Raise if environment variables are missing"""

    def __init__(self, message: str) -> None:
        super().__init__(f"Environment variable(s) used, but not set: {message}")


@define(kw_only=True, frozen=True)
class MetricsConfig:
    """the metrics config class used in Configuration"""

    enabled: bool = field(validator=validators.instance_of(bool), default=False)
    port: int = field(validator=validators.instance_of(int), default=8000)
    uvicorn_config: dict = field(
        validator=[
            validators.instance_of(dict),
            validators.deep_mapping(
                key_validator=validators.in_(http.UVICORN_CONFIG_KEYS),
                # lambda xyz tuple necessary because of input structure
                value_validator=lambda x, y, z: True,
            ),
        ],
        factory=dict,
    )


@define(kw_only=True)
class LoggerConfig:
    """The logger config class used in Configuration.
    The schema for this class is derived from the python logging module:
    https://docs.python.org/3/library/logging.config.html#dictionary-schema-details
    """

    _LOG_LEVELS = (
        logging.NOTSET,  # 0
        logging.DEBUG,  # 10
        logging.INFO,  # 20
        logging.WARNING,  # 30
        logging.ERROR,  # 40
        logging.CRITICAL,  # 50
    )

    version: int = field(validator=validators.instance_of(int), default=1)
    formatters: dict = field(validator=validators.instance_of(dict), factory=dict)
    filters: dict = field(validator=validators.instance_of(dict), factory=dict)
    handlers: dict = field(validator=validators.instance_of(dict), factory=dict)
    disable_existing_loggers: bool = field(validator=validators.instance_of(bool), default=False)
    level: str = field(
        default="INFO",
        validator=[
            validators.instance_of(str),
            validators.in_([logging.getLevelName(level) for level in _LOG_LEVELS]),
        ],
        eq=False,
    )
    """The log level of the root logger. Defaults to :code:`INFO`.

    .. security-best-practice::
       :title: Logprep Log-Level
       :location: config.logger.level
       :suggested-value: INFO

         The log level of the root logger should be set to :code:`INFO` or higher in production environments
         to avoid exposing sensitive information in the logs.
    """
    format: str = field(default="", validator=(validators.instance_of(str)), eq=False)
    """The format of the log message as supported by the :code:`LogprepFormatter`.
    Defaults to :code:`"%(asctime)-15s %(name)-10s %(levelname)-8s: %(message)s"`.

    .. autoclass:: logprep.util.logging.LogprepFormatter
      :no-index:

    """
    datefmt: str = field(default="", validator=(validators.instance_of(str)), eq=False)
    """The date format of the log message. Defaults to :code:`"%Y-%m-%d %H:%M:%S"`."""
    loggers: dict = field(validator=validators.instance_of(dict), factory=dict)
    """The loggers loglevel configuration. Defaults to:

    .. csv-table::

        "root", "INFO"
        "filelock", "ERROR"
        "urllib3.connectionpool", "ERROR"
        "opensearch", "ERROR"
        "uvicorn", "INFO"
        "uvicorn.access", "INFO"
        "uvicorn.error", "INFO"

    You can alter the log level of the loggers by adding them to the loggers mapping like in the
    example. Logprep opts out of hierarchical loggers and so it is possible to set the log level in
    general for all loggers in the :code:`root` logger to :code:`INFO` and then set the log level
    for specific loggers like :code:`Runner` to :code:`DEBUG` to get only DEBUG Messages from the
    Runner instance.

    If you want to silence other loggers like :code:`py.warnings` you can set the log level to
    :code:`ERROR` here.

    .. code-block:: yaml
        :caption: Example of a custom logger configuration

        logger:
            level: ERROR
            format: "%(asctime)-15s %(hostname)-5s %(name)-10s %(levelname)-8s: %(message)s"
            datefmt: "%Y-%m-%d %H:%M:%S"
            loggers:
                "py.warnings": {"level": "ERROR"}
                "Runner": {"level": "DEBUG"}

        """

    def __attrs_post_init__(self) -> None:
        """Create a LoggerConfig from a logprep logger configuration."""
        self._set_defaults()
        if not self.level:
            self.level = DEFAULT_LOG_CONFIG.get("loggers", {}).get("root", {}).get("level", "INFO")
        if self.loggers:
            self._set_loggers_levels()
        self.loggers = {**DEFAULT_LOG_CONFIG["loggers"] | self.loggers}
        self.loggers.get("root", {}).update({"level": self.level})

    def setup_logging(self) -> None:
        """Setup the logging configuration.
        is called in the :code:`logprep.run_logprep` module.
        We have to write the configuration to the environment variable :code:`LOGPREP_LOG_CONFIG` to
        make it available for the uvicorn server in :code:'logprep.util.http'.
        """
        log_config = asdict(self)
        os.environ["LOGPREP_LOG_CONFIG"] = json.dumps(log_config)
        dictConfig(log_config)

    def _set_loggers_levels(self) -> None:
        """sets the loggers levels to the default or to the given level."""
        for logger_name, logger_config in self.loggers.items():
            default_logger_config = deepcopy(DEFAULT_LOG_CONFIG.get(logger_name, {}))
            if "level" in logger_config:
                default_logger_config.update({"level": logger_config["level"]})
            self.loggers[logger_name].update(default_logger_config)

    def _set_defaults(self) -> None:
        """resets all keys to the defined defaults except :code:`loggers`."""
        for key, value in DEFAULT_LOG_CONFIG.items():
            if key == "loggers":
                continue
            setattr(self, key, value)


@define(kw_only=True)
class Configuration:
    """the configuration class"""

    version: str = field(
        validator=validators.instance_of(str), converter=str, default="unset", eq=True
    )
    """It is optionally possible to set a version to your configuration file which
    can be printed via :code:`logprep run --version config/pipeline.yml`.
    This has no effect on the execution of logprep and is merely used for documentation purposes.
    Defaults to :code:`unset`."""
    config_refresh_interval: Optional[int] = field(
        validator=validators.instance_of((int, type(None))), default=None, eq=False
    )
    """Configures the interval in seconds on which logprep should try to reload the configuration.
    If not configured, logprep won't reload the configuration automatically.
    If configured the configuration will only be reloaded if the configuration version changes.
    If http errors occurs on configuration reload `config_refresh_interval` is set to a quarter
    of the current `config_refresh_interval` until a minimum of 5 seconds is reached.
    Defaults to :code:`None`, which means that the configuration will not be refreshed.

    .. security-best-practice::
       :title: Configuration Refresh Interval
       :location: config.config_refresh_interval
       :suggested-value: <= 300

       The refresh interval for the configuration shouldn't be set too high in production
       environments.
       It is suggested to not set a value higher than :code:`300` (5 min).
       That way configuration updates are propagated fairly quickly instead of once a day.

       It should also be noted that a new configuration file will be read as long as it is a valid
       config.
       There is no further check to ensure credibility.

       In case a new configuration could not be retrieved successfully and the
       :code:`config_refresh_interval` is already reduced automatically to 5 seconds it should be
       noted that this could lead to a blocking behavior or an significant reduction in performance
       as logprep is often retrying to reload the configuration.
       Because of that ensure that the configuration endpoint is always available.
    """
    process_count: int = field(
        validator=(validators.instance_of(int), validators.ge(1)), default=1, eq=False
    )
    """Number of logprep processes to start. Defaults to :code:`1`."""
    restart_count: int = field(
        validator=validators.instance_of(int), default=DEFAULT_RESTART_COUNT, eq=False
    )
    """Number of restarts before logprep exits. Defaults to :code:`5`.
    If this value is set to a negative number, logprep will always restart immediately."""
    timeout: float = field(
        validator=(validators.instance_of(float), validators.gt(0)), default=5.0, eq=False
    )
    """Logprep tries to react to signals (like sent by CTRL+C) within the given time.
    The time taken for some processing steps is not always predictable, thus it is not possible to
    ensure that this time will be adhered to.
    However, Logprep reacts quickly for small values (< 1.0), but this requires more
    processing power. This can be useful for testing and debugging.
    Larger values (like 5.0) slow the reaction time down, but this requires less processing power,
    which makes in preferable for continuous operation. Defaults to :code:`5.0`."""
    logger: LoggerConfig = field(
        validator=validators.instance_of(LoggerConfig),
        default=LoggerConfig(**DEFAULT_LOG_CONFIG),
        eq=False,
        converter=lambda x: LoggerConfig(**x) if isinstance(x, dict) else x,
    )
    """Logger configuration.

    .. autoclass:: logprep.util.configuration.LoggerConfig
       :no-index:
       :no-undoc-members:
       :members: level, format, datefmt, loggers

    """
    input: dict = field(validator=validators.instance_of(dict), factory=dict, eq=False)
    """
    Input connector configuration. Defaults to :code:`{}`.
    For detailed configurations see :ref:`input`.
    """
    output: dict = field(validator=validators.instance_of(dict), factory=dict, eq=False)
    """
    Output connector configuration. Defaults to :code:`{}`.
    For detailed configurations see :ref:`output`.
    """
    error_output: dict = field(validator=validators.instance_of(dict), factory=dict, eq=False)
    """
    Error output connector configuration. Defaults to :code:`{}`.
    This is optional. If no error output is configured, logprep will not handle events that
    could not be processed by the pipeline, not parsed correctly by input connectors or not
    stored correctly by output connectors.
    For detailed configurations see :ref:`output`.
    """
    pipeline: list[dict] = field(validator=validators.instance_of(list), factory=list, eq=False)
    """
    Pipeline configuration. Defaults to :code:`[]`.
    See :ref:`processors` for a detailed overview on how to configure a pipeline.
    """
    metrics: MetricsConfig = field(
        validator=validators.instance_of(MetricsConfig),
        factory=MetricsConfig,
        converter=lambda x: MetricsConfig(**x) if isinstance(x, dict) else x,
        eq=False,
    )
    """Metrics configuration. Defaults to
    :code:`{"enabled": False, "port": 8000, "uvicorn_config": {}}`.

    The key :code:`uvicorn_config` can be configured with any uvicorn config parameters.
    For further information see the `uvicorn documentation <https://www.uvicorn.org/settings/>`_.

    .. security-best-practice::
       :title: Metrics Configuration
       :location: config.metrics.uvicorn_config
       :suggested-value: metrics.uvicorn_config.access_log: true, metrics.uvicorn_config.server_header: false, metrics.uvicorn_config.data_header: false

       Additionally to the below it is recommended to configure `ssl on the metrics server endpoint
       <https://www.uvicorn.org/settings/#https>`_

       .. code-block:: yaml

          metrics:
            enabled: true
            port: 9000
            uvicorn_config:
              access_log: true
              server_header: false
              date_header: false
              workers: 1

    """
    profile_pipelines: bool = field(default=False, eq=False)
    """Start the profiler to profile the pipeline. Defaults to :code:`False`."""
    print_auto_test_stack_trace: bool = field(default=False, eq=False)
    """Print stack trace when auto test fails. Defaults to :code:`False`."""
    error_backlog_size: int = field(
        validator=validators.instance_of(int), default=DEFAULT_MESSAGE_BACKLOG_SIZE, eq=False
    )
    """Size of the error backlog. Defaults to :code:`15000`."""

    _metrics: "Configuration.Metrics" = field(init=False, repr=False, eq=False)

    _getter: Getter = field(
        validator=validators.instance_of(Getter),
        default=GetterFactory.from_string(DEFAULT_CONFIG_LOCATION),
        repr=False,
        eq=False,
    )

    _configs: Tuple["Configuration", ...] = field(
        validator=validators.instance_of(tuple), factory=tuple, repr=False, eq=False
    )

    _scheduler: Scheduler = field(
        factory=Scheduler,
        validator=validators.instance_of(Scheduler),
        repr=False,
        eq=False,
        init=False,
    )

    _config_failure: bool = field(default=False, repr=False, eq=False, init=False)

    _unserializable_fields = (
        "_getter",
        "_configs",
        "_config_failure",
        "_scheduler",
        "_metrics",
        "_unserializable_fields",
    )

    @define(kw_only=True)
    class Metrics(Component.Metrics):
        """Metrics for the Logprep Runner."""

        version_info: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Logprep version information",
                name="version_info",
                labels={"logprep": "unset", "config": "unset"},
                inject_label_values=False,
            )
        )
        """Logprep version info."""
        config_refresh_interval: GaugeMetric = field(
            factory=lambda: GaugeMetric(
                description="Logprep config refresh interval",
                name="config_refresh_interval",
                labels={"from": "unset", "config": "unset"},
            )
        )
        """Indicates the configuration refresh interval in seconds."""
        number_of_config_refreshes: CounterMetric = field(
            factory=lambda: CounterMetric(
                description="Indicates how often the logprep configuration was updated.",
                name="number_of_config_refreshes",
                labels={"from": "unset", "config": "unset"},
            )
        )
        """Indicates how often the logprep configuration was updated."""
        number_of_config_refresh_failures: CounterMetric = field(
            factory=lambda: CounterMetric(
                description=(
                    "Indicates how often the logprep configuration "
                    "could not be updated due to failures during the update."
                ),
                name="number_of_config_refresh_failures",
                labels={"from": "unset", "config": "unset"},
            )
        )
        """Indicates how often the logprep configuration could not be updated
          due to failures during the update."""

    def __attrs_post_init__(self) -> None:
        self._metrics = self.Metrics(labels={"logprep": "unset", "config": "unset"})
        self._set_version_info_metric()
        self._set_config_refresh_interval(self.config_refresh_interval)

    @property
    def _metric_labels(self) -> dict[str, str]:
        labels = {
            "logprep": f"{version('logprep')}",
            "config": f"{self.version}",
        }
        return labels

    @property
    def config_paths(self) -> list[str]:
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
    def from_source(cls, config_path: str) -> "Configuration":
        """Create configuration from an uri source.

        Parameters
        ----------
        config_path : str
            uri of file to create configuration from.

        Returns
        -------
        config : Configuration
            Configuration object attrs class.

        """
        try:
            config_getter = GetterFactory.from_string(config_path)
            try:
                config_dict = config_getter.get_json()
            except (json.JSONDecodeError, ValueError):
                config_dict = config_getter.get_yaml()
            config = Configuration(**(config_dict | {"getter": config_getter}))
        except TypeError as error:
            raise InvalidConfigurationError(
                f"Invalid configuration file: {config_path} {error.args[0]}"
            ) from error
        except ValueError as error:
            raise InvalidConfigurationError(
                f"Invalid configuration file: {config_path} {str(error)}"
            ) from error
        config._configs = (config,)
        return config

    @classmethod
    def from_sources(cls, config_paths: Iterable[str] | None = None) -> "Configuration":
        """Creates configuration from a list of configuration sources.

        Parameters
        ----------
        config_paths : list[str]
            List of configuration sources (URI) to create configuration from.

        Returns
        -------
        config : Configuration
            resulting configuration object.

        """
        if not config_paths:
            config_paths = [DEFAULT_CONFIG_LOCATION]
        errors = []
        configs: List[Configuration] = []
        for config_path in config_paths:
            try:
                config = Configuration.from_source(config_path)
                configs.append(config)
            except (GetterNotFoundError, RequestException, CredentialsEnvNotFoundError) as error:
                raise ConfigGetterException(f"{config_path} {error}") from error
            except FileNotFoundError as error:
                raise ConfigGetterException(
                    f"One or more of the given config file(s) does not exist: {error.filename}\n",
                ) from error
            except ScannerError as error:
                raise ConfigGetterException(
                    f"Invalid yaml or json file: {config_path} {error.problem}\n"
                ) from error
            except InvalidConfigurationError as error:
                errors.append(error)
        configuration = Configuration()
        configuration._configs = tuple(configs)
        configuration._set_attributes_from_configs()
        try:
            configuration._build_merged_pipeline()
        except InvalidConfigurationErrors as error:
            errors = [*errors, *error.errors]
        try:
            configuration._verify()
        except InvalidConfigurationErrors as error:
            errors = [*errors, *error.errors]
        if errors:
            raise InvalidConfigurationErrors(errors)
        return configuration

    def as_dict(self) -> dict:
        """Return the configuration as dict."""
        return asdict(
            self,
            filter=lambda attribute, _: attribute.name not in self._unserializable_fields,
            recurse=True,
        )

    def as_json(self, indent=None) -> str:
        """Return the configuration as json string."""
        return json.dumps(self.as_dict(), indent=indent)

    def as_yaml(self) -> str:
        """Return the configuration as yaml string."""
        return yaml.dump(self.as_dict())

    def reload(self) -> None:
        """Reloads the application's configuration from the specified sources.

        This method attempts to reload the application's configuration by reading from the
        configured paths or urls. If the new configuration is identical to the current one, it
        simply updates the refresh interval and continues. If the configuration has changed, it
        updates the internal state, metrics, and pipeline accordingly.

        In case of a failure to load the configuration, it logs the error, updates failure metrics,
        and, if possible, reduces the configuration refresh interval to attempt more frequent
        retries.

        The configuration refresh interval (:code:`config_refresh_interval`) determines how often
        the configuration should be reloaded. If the configuration reload fails, the interval is
        temporarily reduced to a quarter of its previous value to allow for quicker recovery. If
        the reload is successful or the configuration hasn't changed, the interval is set or
        maintained according to the latest configuration.

        Note
        ----
        The `config_refresh_interval` in the new configuration cannot be set to `None` because it
        is required to control the periodic reloads of the configuration. If it is missing in the
        new configuration, the previous interval is retained to ensure the reload mechanism
        continues to function.

        Raises
        ------
        ConfigGetterException
            If there is an error retrieving the configuration.
        InvalidConfigurationErrors
            If the configuration is invalid.
        """
        errors: List[Exception] = []
        try:
            new_config = Configuration.from_sources(self.config_paths)
            if self._config_failure:
                logger.info("Config refresh recovered from failing source")
            self._config_failure = False
            if new_config == self:
                logger.info(
                    "Configuration version didn't change. Continue running with current version."
                )
                self._set_config_refresh_interval(new_config.config_refresh_interval)
                return
            if new_config.config_refresh_interval is None:
                new_config.config_refresh_interval = self.config_refresh_interval
            self._configs = new_config._configs  # pylint: disable=protected-access
            self._set_attributes_from_configs()
            self._set_version_info_metric()
            self.pipeline = new_config.pipeline
            self._metrics.number_of_config_refreshes += 1
            logger.info("Successfully reloaded configuration")
            logger.info("Configuration version: %s", self.version)
            self._set_config_refresh_interval(new_config.config_refresh_interval)
        except ConfigGetterException as error:
            self._config_failure = True
            logger.warning("Failed to load configuration: %s", error)
            self._metrics.number_of_config_refresh_failures += 1
            if self.config_refresh_interval is not None:
                self._set_config_refresh_interval(int(self.config_refresh_interval / 4))
        except InvalidConfigurationErrors as error:
            self._config_failure = True
            errors = [*errors, *error.errors]
        if errors:
            logger.error("Failed to reload configuration: %s", errors)
            self._metrics.number_of_config_refresh_failures += 1

    def _set_config_refresh_interval(self, config_refresh_interval: int | None) -> None:
        if config_refresh_interval is None:
            return
        config_refresh_interval = max(config_refresh_interval, MIN_CONFIG_REFRESH_INTERVAL)
        self.config_refresh_interval = config_refresh_interval
        self.schedule_config_refresh()
        self._metrics.config_refresh_interval += config_refresh_interval

    def schedule_config_refresh(self) -> None:
        """
        Schedules a periodic configuration refresh based on the specified interval.

        Cancels any existing scheduled configuration refresh job and schedules a new one
        using the current :code:`config_refresh_interval`.
        The refresh job will call the :code:`reload` method at the specified interval
        in seconds on invoking the :code:`refresh` method.

        Notes
        -----
        - Only one configuration refresh job is scheduled at a time
        - Any existing job is cancelled before scheduling a new one.
        - The interval must be an integer representing seconds.

        Examples
        --------
        >>> self.schedule_config_refresh()
        Config refresh interval is set to: 60 seconds
        """
        scheduler = self._scheduler
        if self.config_refresh_interval is None:
            if scheduler.jobs:
                scheduler.cancel_job(scheduler.jobs[0])
            return

        self.config_refresh_interval = max(
            self.config_refresh_interval, MIN_CONFIG_REFRESH_INTERVAL
        )
        refresh_interval = self.config_refresh_interval
        if scheduler.jobs:
            scheduler.cancel_job(scheduler.jobs[0])
        if isinstance(refresh_interval, int):
            scheduler.every(refresh_interval).seconds.do(self.reload)
            logger.info("Config refresh interval is set to: %s seconds", refresh_interval)

    def refresh(self) -> None:
        """Wrap the scheduler run_pending method hide the implementation details."""
        self._scheduler.run_pending()

    def _set_attributes_from_configs(self) -> None:
        for attribute in filter(lambda x: x.repr, fields(self.__class__)):
            setattr(
                self,
                attribute.name,
                self._get_last_non_default_value(self._configs, attribute.name),
            )
        versions = (config.version for config in self._configs if config.version)
        self.version = ", ".join(versions)

    def _build_merged_pipeline(self) -> None:
        pipelines = (config.pipeline for config in self._configs if config.pipeline)
        pipeline = list(chain(*pipelines))
        errors = []
        pipeline_with_loaded_rules = []
        for processor_definition in pipeline:
            try:
                processor_definition_with_rules = self._load_rule_definitions(processor_definition)
                pipeline_with_loaded_rules.append(processor_definition_with_rules)
            except (FactoryError, TypeError, ValueError, InvalidRuleDefinitionError) as error:
                errors.append(error)
        if errors:
            raise InvalidConfigurationErrors(errors)
        self.pipeline = pipeline_with_loaded_rules

    def _load_rule_definitions(self, processor_definition: dict) -> dict:
        processor_definition = deepcopy(processor_definition)
        _ = Factory.create(processor_definition)
        processor_name, processor_config = processor_definition.popitem()
        rule_sources = processor_config.get("rules", [])
        rules_definitions = RuleLoader(rule_sources, processor_name).rule_definitions
        processor_config["rules"] = rules_definitions
        return {processor_name: processor_config}

    @staticmethod
    def _get_last_non_default_value(configs: Sequence["Configuration"], attribute: str) -> Any:
        if configs:
            config = configs[0]
            attrs_attribute = [attr for attr in fields(config.__class__) if attr.name == attribute][
                0
            ]
            default_for_attribute = (
                attrs_attribute.default.factory()
                if hasattr(attrs_attribute.default, "factory")
                else attrs_attribute.default
            )
            values = [getattr(config, attribute) for config in configs]
            for value in reversed(values):
                if value != default_for_attribute:
                    return value
            return values[-1]
        return getattr(Configuration(), attribute)

    def _verify(self) -> None:
        """Verify the configuration."""
        errors: list[Exception] = []
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
        if self.error_output:
            for output_name, output_config in self.error_output.items():
                try:
                    Factory.create({output_name: output_config})
                except Exception as error:  # pylint: disable=broad-except
                    errors.append(error)
        for processor_config in self.pipeline:
            try:
                processor = Factory.create(deepcopy(processor_config))
                processor.setup()
                self._verify_rules(processor)
            except (FactoryError, TypeError, ValueError, InvalidRuleDefinitionError) as error:
                errors.append(error)
            except FileNotFoundError as error:
                errors.append(InvalidConfigurationError(f"File not found: {error.filename}"))
            try:
                self._verify_processor_outputs(processor_config)
            except Exception as error:  # pylint: disable=broad-except
                errors.append(error)
        if ENV_NAME_LOGPREP_CREDENTIALS_FILE in os.environ:
            try:
                credentials_file_path = os.environ.get(ENV_NAME_LOGPREP_CREDENTIALS_FILE)
                _ = CredentialsFactory.get_content(Path(credentials_file_path))
            except Exception as error:  # pylint: disable=broad-except
                errors.append(error)
        if errors:
            raise InvalidConfigurationErrors(errors)

    def _verify_processor_outputs(self, processor_config) -> None:
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

    def _verify_environment(self) -> None:
        # pylint: disable=protected-access
        getters = (config._getter for config in self._configs if config._getter)
        # pylint: enable=protected-access
        missing_env_vars = tuple(chain(*[getter.missing_env_vars for getter in getters]))
        if missing_env_vars:
            raise MissingEnvironmentError(", ".join(missing_env_vars))
        if "PROMETHEUS_MULTIPROC_DIR" in os.environ:
            prometheus_multiproc_path = os.environ["PROMETHEUS_MULTIPROC_DIR"]
            if not Path(prometheus_multiproc_path).exists():
                raise InvalidConfigurationError(
                    (
                        "PROMETHEUS_MULTIPROC_DIR is set, but "
                        f"'{prometheus_multiproc_path}' does not exist"
                    )
                )
        if self.metrics.enabled:
            if "PROMETHEUS_MULTIPROC_DIR" not in os.environ:
                raise InvalidConfigurationError(
                    "Metrics enabled but PROMETHEUS_MULTIPROC_DIR is not set"
                )

    def _verify_rules(self, processor: Processor) -> None:
        rule_ids = []
        for rule in processor.rules:
            if rule.id in rule_ids:
                raise InvalidRuleDefinitionError(f"Duplicate rule id: {rule.id}, {rule}")
            rule_ids.append(rule.id)
            if not hasattr(processor.rule_class, "outputs"):
                continue
            self._verify_outputs(processor, rule)

    def _verify_outputs(self, processor: Processor, rule) -> None:
        for output in rule.outputs:
            for output_name, _ in output.items():
                if output_name not in self.output:
                    raise InvalidRuleDefinitionError(
                        f"{processor.describe()}: output"
                        f" '{output_name}' does not exist in logprep outputs"
                    )

    def _set_version_info_metric(self) -> None:
        self._metrics.version_info.add_with_labels(
            1,
            {"logprep": f"{version('logprep')}", "config": self.version},
        )
