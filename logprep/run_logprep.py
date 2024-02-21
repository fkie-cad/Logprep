# pylint: disable=logging-fstring-interpolation
"""This module can be used to start the logprep."""
import logging
import os
import signal
import sys
import tempfile
import warnings
from pathlib import Path

import click
from colorama import Fore

from logprep.event_generator.http.controller import Controller
from logprep.event_generator.kafka.run_load_tester import LoadTester
from logprep.runner import Runner
from logprep.util.auto_rule_tester.auto_rule_corpus_tester import RuleCorpusTester
from logprep.util.auto_rule_tester.auto_rule_tester import AutoRuleTester
from logprep.util.configuration import Configuration, InvalidConfigurationError
from logprep.util.helper import get_versions_string, print_fcolor
from logprep.util.rule_dry_runner import DryRunner

warnings.simplefilter("always", DeprecationWarning)
logging.captureWarnings(True)

logging.getLogger("filelock").setLevel(logging.ERROR)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("elasticsearch").setLevel(logging.ERROR)


EPILOG_STR = "Check out our docs at https://logprep.readthedocs.io/en/latest/"


def _print_version(config: "Configuration") -> None:
    print(get_versions_string(config))
    sys.exit(0)


def _get_logger(logger_config: dict) -> logging.Logger:
    log_level = logger_config.get("level", "INFO")
    logging.basicConfig(
        level=log_level, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s"
    )
    logger = logging.getLogger("Logprep")
    logger.setLevel(log_level)
    return logger


def _get_configuration(config_paths: list[str]) -> Configuration:
    try:
        return Configuration.from_sources(config_paths)
    except InvalidConfigurationError as error:
        print(f"InvalidConfigurationError: {error}", file=sys.stderr)
        sys.exit(1)


@click.group(name="logprep")
@click.version_option(version=get_versions_string(), message="%(version)s")
def cli() -> None:
    """
    Logprep allows to collect, process and forward log messages from various data sources.
    Log messages are being read and written by so-called connectors.
    """


@cli.command(short_help="Run logprep to process log messages", epilog=EPILOG_STR)
@click.argument("configs", nargs=-1, required=False)
@click.option(
    "--version",
    is_flag=True,
    default=False,
    help="Print version and exit (includes also congfig version)",
)
def run(configs: tuple[str], version=None) -> None:
    """
    Run Logprep with the given configuration.

    CONFIG is a path to configuration file (filepath or URL).
    """
    configuration = _get_configuration(configs)
    if version:
        _print_version(configuration)
    logger = _get_logger(configuration.logger)
    logger.info(f"Log level set to '{logging.getLevelName(logger.level)}'")
    for version in get_versions_string(configuration).split("\n"):
        logger.info(version)
    logger.debug(f"Metric export enabled: {configuration.metrics.enabled}")
    logger.debug(f"Config path: {configs}")
    runner = None
    try:
        runner = Runner.get_runner(configuration)
        logger.debug("Configuration loaded")
        runner.start()
    # pylint: disable=broad-except
    except Exception as error:
        if os.environ.get("DEBUG", False):
            logger.exception(f"A critical error occurred: {error}")  # pragma: no cover
        else:
            logger.critical(f"A critical error occurred: {error}")
        if runner:
            runner.stop()
        sys.exit(1)
    # pylint: enable=broad-except


@cli.group(name="test", short_help="Execute tests against a given configuration")
def test() -> None:
    """
    Execute certain tests like unit and integration tests. Can also verify the configuration.
    """


@test.command(name="config")
@click.argument("configs", nargs=-1)
def test_config(configs: tuple[str]) -> None:
    """
    Verify the configuration file

    CONFIG is a path to configuration file (filepath or URL).
    """
    _get_configuration(configs)
    print_fcolor(Fore.GREEN, "The verification of the configuration was successful")


@test.command(short_help="Execute a dry run against a configuration and selected events")
@click.argument("configs", nargs=-1)
@click.argument("events")
@click.option(
    "--input-type",
    help="Specifies the input type.",
    type=click.Choice(["json", "jsonl"]),
    default="jsonl",
    show_default=True,
)
@click.option(
    "--full-output",
    help="Print full dry-run output, including all extra output",
    default=True,
    type=click.BOOL,
    show_default=True,
)
def dry_run(configs: tuple[str], events: str, input_type: str, full_output: bool) -> None:
    """
    Execute a logprep dry run with the given configuration against a set of events. The results of
    the processing will be printed in the terminal.

    \b
    CONFIG is a path to configuration file (filepath or URL).
    EVENTS is a path to a 'json' or 'jsonl' file.
    """
    config = _get_configuration(configs)
    json_input = input_type == "json"
    dry_runner = DryRunner(events, config, full_output, json_input, logging.getLogger("DryRunner"))
    dry_runner.run()


@test.command(short_help="Run the rule tests of the given configurations", name="unit")
@click.argument("configs", nargs=-1)
def test_rules(configs: tuple[str]) -> None:
    """
    Test rules against their respective test files

    CONFIG is a path to configuration file (filepath or URL).
    """
    _get_configuration(configs)
    for config in configs:
        tester = AutoRuleTester(config)
        tester.run()


@test.command(
    short_help="Run the rule corpus tester against a given configuration", name="integration"
)
@click.argument("configs", nargs=-1, required=False)
@click.argument("testdata")
def test_ruleset(configs: tuple[str], testdata: str):
    """Test the given ruleset against specified test data

    \b
    CONFIG is a path to configuration file (filepath or URL).
    TESTDATA is a path to a set of test files.
    """
    _ = _get_configuration(configs)
    tester = RuleCorpusTester(configs, testdata)
    tester.run()


@cli.group(short_help="Generate load for a running logprep instance")
def generate():
    """
    Generate events offers two different options to create sample events that can be send to either
    a kafka instance or a http endpoint.
    """


@generate.command(name="kafka")
@click.argument("config")
@click.option(
    "--file", help="Path to file with documents", default=None, type=click.Path(exists=True)
)
def generate_kafka(config, file):
    """
    Generate events by taking them from kafka or a jsonl file and sending them to Kafka.

    CONFIG is a path to a configuration file for the event generation.
    """
    load_tester = LoadTester(config, file)
    load_tester.run()


@generate.command(name="http")
@click.option("--input-dir", help="Path to the root input directory", required=True, type=str)
@click.option(
    "--target-url",
    help="Target root url where all events should be send to. The specific path of each log class "
    "will be appended to it, resulting in the complete url that should be used as an endpoint.",
    required=True,
    type=str,
)
@click.option("--user", help="Username for the target domain", required=True, type=str)
@click.option(
    "--password", help="Credentials for the user of the target domain", required=True, type=str
)
@click.option(
    "--batch-size",
    help="Number of events that should be loaded and send as a batch. Exact number of events "
    "per request will differ as they are separated by log class. If a log class has more "
    "samples than another log class, it will also have a larger request size.",
    required=False,
    default=500,
    type=int,
)
@click.option(
    "--events",
    help="Total number of events that should be send to the target.",
    required=False,
    default=None,
    type=int,
)
@click.option(
    "--shuffle",
    help="Shuffle the events before sending them to the target.",
    required=False,
    default=False,
    type=bool,
)
@click.option(
    "--thread_count",
    help="Number of threads that should be used to send events in parallel to the target. If "
    "thread_count is set to '1' then multithreading is deactivated and the main process will "
    "be used.",
    required=False,
    default=1,
    type=int,
)
@click.option(
    "--replace-timestamp",
    help="Defines if timestamps should be replaced with the current timestamp.",
    required=False,
    default=True,
    type=bool,
)
@click.option(
    "--tag",
    help="Tag that should be written into the events.",
    required=False,
    default="loadtest",
    type=str,
)
@click.option(
    "--loglevel",
    help="Sets the log level for the logger.",
    type=click.Choice(logging._levelToName.values()),
    required=False,
    default="INFO",
)
@click.option(
    "--report",
    help="Whether or not detailed statistics with a markdown report should be generated or not.",
    required=False,
    default=True,
    type=bool,
)
def generate_http(**kwargs):
    """
    Generates events based on templated sample files stored inside a dataset directory.
    The events will be sent to a http endpoint.
    """
    log_level = kwargs.get("loglevel")
    logging.basicConfig(
        level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logger = logging.getLogger("generator")
    logger.info(f"Log level set to '{log_level}'")
    generator = Controller(**kwargs)
    generator.run()


@cli.command(short_help="Print a complete configuration file [Not Yet Implemented]", name="print")
@click.argument("configs", nargs=-1, required=True)
@click.option(
    "--output",
    type=click.Choice(["json", "yaml"]),
    default="yaml",
    help="What output format to use",
)
def print_config(configs: tuple[str], output) -> None:
    """
    Prints the given configuration as a combined yaml or json file, with all rules and options
    included.

    CONFIG is a path to configuration file (filepath or URL).
    """
    config = _get_configuration(configs)
    if output == "json":
        print(config.as_json(indent=2))
    else:
        print(config.as_yaml())


def signal_handler(__: int, _) -> None:
    """Handle signals for stopping the runner and reloading the configuration."""
    Runner.get_runner(Configuration()).stop()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    cli()
