# pylint: disable=logging-fstring-interpolation
"""This module can be used to start the logprep."""
import logging
import os
import sys
import warnings

import click
import requests
from colorama import Fore

from logprep.runner import Runner
from logprep.util.auto_rule_tester.auto_rule_corpus_tester import RuleCorpusTester
from logprep.util.auto_rule_tester.auto_rule_tester import AutoRuleTester
from logprep.util.configuration import Configuration, InvalidConfigurationError
from logprep.util.getter import GetterNotFoundError
from logprep.util.configuration import (
    Configuration,
    InvalidConfigurationError,
    InvalidConfigurationErrors,
)
from logprep.util.configuration import Configuration, InvalidConfigurationError
from logprep.util.defaults import DEFAULT_CONFIG_LOCATION
from logprep.util.helper import get_versions_string, print_fcolor
from logprep.util.rule_dry_runner import DryRunner

warnings.simplefilter("always", DeprecationWarning)
logging.captureWarnings(True)

logging.getLogger("filelock").setLevel(logging.ERROR)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("elasticsearch").setLevel(logging.ERROR)


EPILOG_STR = "Check out our docs at https://logprep.readthedocs.io/en/latest/"


def print_version_and_exit(config):
    print(get_versions_string(config))
    sys.exit(0)


def _get_logger(logger_config: dict):
    log_level = logger_config.get("level", "INFO")
    logging.basicConfig(
        level=log_level, format="%(asctime)-15s %(name)-5s %(levelname)-8s: %(message)s"
    )
    logger = logging.getLogger("Logprep")
    return logger


def _load_configuration(config_paths: list[str]):
    try:
        return Configuration.from_sources(config_paths)
    except FileNotFoundError:
        print(
            f"One or more of the given config file(s) does not exist: {', '.join(config_paths)}",
            file=sys.stderr,
        )
        print(
            "Create the configuration or change the path. Use '--help' for more information.",
            file=sys.stderr,
        )
        sys.exit(1)
    except GetterNotFoundError as error:
        print(f"{error}", file=sys.stderr)
    except requests.RequestException as error:
        print(f"{error}", file=sys.stderr)
    return None


@click.group(name="logprep")
@click.version_option(version=get_versions_string(), message="%(version)s")
def cli():
    """
    Logprep allows to collect, process and forward log messages from various data sources.
    Log messages are being read and written by so-called connectors.
    """


@cli.command(short_help="Run logprep to process log messages", epilog=EPILOG_STR)
@click.argument("config", nargs=-1, required=True)
@click.option(
    "--version",
    is_flag=True,
    default=False,
    help="Print version and exit (includes also congfig version)",
)
def run(config: str, version=None):
    """
    Run Logprep with the given configuration.

    CONFIG is a path to configuration file (filepath or URL).
    """
    config_obj = _load_configuration(config)
    if version:
        print_version_and_exit(config_obj)
    logger = _get_logger(config_obj.logger)
    logger.info(f"Log level set to '{logger.level}'")
    for version in get_versions_string(config).split("\n"):
        logger.info(version)
    logger.debug(f'Metric export enabled: {config_obj.get("metrics", {}).get("enabled", False)}')
    logger.debug(f"Config path: {config}")
    runner = None
    try:
        runner = Runner.get_runner()
        runner.load_configuration(config)
        logger.debug("Configuration loaded")
        runner.start()
    # pylint: disable=broad-except
    except BaseException as error:
        if os.environ.get("DEBUG", False):
            logger.exception(f"A critical error occurred: {error}")  # pragma: no cover
        else:
            logger.critical(f"A critical error occurred: {error}")
        if runner:
            runner.stop()
        sys.exit(1)
    # pylint: enable=broad-except


@cli.group(name="test", short_help="Execute tests against a given configuration")
def test():
    """
    Execute certain tests like unit and integration tests. Can also verify the configuration.
    """


@test.command(name="config")
@click.argument("config")
def test_config(config):
    """
    Verify the configuration file

    CONFIG is a path to configuration file (filepath or URL).
    """
    config = _load_configuration(config)
    logger = _setup_logger(config)
    try:
        config.verify(logger=logger)
    except InvalidConfigurationError as error:
        logger.critical(error)
        sys.exit(1)
    print_fcolor(Fore.GREEN, "The verification of the configuration was successful")


@test.command(short_help="Execute a dry run against a configuration and selected events")
@click.argument("config")
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
def dry_run(config, events, input_type, full_output):
    """
    Execute a logprep dry run with the given configuration against a set of events. The results of
    the processing will be printed in the terminal.

    \b
    CONFIG is a path to configuration file (filepath or URL).
    EVENTS is a path to a 'json' or 'jsonl' file.
    """
    json_input = input_type == "json"
    dry_runner = DryRunner(events, config, full_output, json_input, logging.getLogger("DryRunner"))
    dry_runner.run()


@test.command(short_help="Run the rule tests of the given configuration", name="unit")
@click.argument("config")
def test_rules(config):
    """
    Test rules against their respective test files

    CONFIG is a path to configuration file (filepath or URL).
    """
    tester = AutoRuleTester(config)
    tester.run()


@test.command(
    short_help="Run the rule corpus tester against a given configuration", name="integration"
)
@click.argument("config")
@click.argument("testdata")
def test_ruleset(config, testdata):
    """Test the given ruleset against specified test data

    \b
    CONFIG is a path to configuration file (filepath or URL).
    TESTDATA is a path to a set of test files.
    """
    tester = RuleCorpusTester(config, testdata)
    tester.run()


@cli.command(short_help="Generate load for a running logprep instance [Not Yet Implemented]")
def generate():
    """
    Generate load offers two different options to create sample events for a running
    logprep instance.
    """
    raise NotImplementedError


@cli.command(short_help="Print a complete configuration file [Not Yet Implemented]", name="print")
@click.argument("config")
@click.option(
    "--output",
    type=click.Choice(["json", "yaml"]),
    default="yaml",
    help="What output format to use",
)
def print_config(config, output):
    """
    Prints the given configuration as a combined yaml or json file, with all rules and options
    included.

    CONFIG is a path to configuration file (filepath or URL).
    """
    raise NotImplementedError


if __name__ == "__main__":
    cli()
