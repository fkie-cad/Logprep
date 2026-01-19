# pylint: disable=logging-fstring-interpolation
"""This module can be used to start the logprep."""

import logging
import os
import signal
import sys
from multiprocessing import set_start_method

import click

from logprep.ng.runner import Runner
from logprep.ng.util.configuration import Configuration, InvalidConfigurationError
from logprep.util.defaults import EXITCODES
from logprep.util.helper import get_versions_string
from logprep.util.tag_yaml_loader import init_yaml_loader_tags

EPILOG_STR = "Check out our docs at https://logprep.readthedocs.io/en/latest/"
init_yaml_loader_tags("safe", "rt")


logger = logging.getLogger("root")


def _print_version(config: "Configuration") -> None:
    print(get_versions_string(config))
    sys.exit(EXITCODES.SUCCESS)


def _get_configuration(config_paths: tuple[str]) -> Configuration:
    try:
        config = Configuration.from_sources(config_paths)
        logger.info("Log level set to '%s'", config.logger.level)
        return config
    except InvalidConfigurationError as error:
        logger.error("InvalidConfigurationError: %s", error)
        sys.exit(EXITCODES.CONFIGURATION_ERROR)


@click.group(name="logprep")
@click.version_option(version=get_versions_string(), message="%(version)s")
def cli() -> None:
    """
    Logprep allows to collect, process and forward log messages from various data sources.
    Log messages are being read and written by so-called connectors.
    """

    set_start_method("fork", force=True)

    if "pytest" not in sys.modules:  # needed for not blocking tests
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)


@cli.command(short_help="Run logprep ng to process log messages", epilog=EPILOG_STR)
@click.argument("configs", nargs=-1, required=False)
@click.option(
    "--version",
    is_flag=True,
    default=False,
    help="Print version and exit (includes also config version)",
)
def run(configs: tuple[str], version=None) -> None:
    """
    Run Logprep with the given configuration.

    CONFIG is a path to configuration file (filepath or URL).
    """
    configuration = _get_configuration(configs)
    runner = Runner(configuration)
    runner.setup_logging()
    if version:
        _print_version(configuration)
    for version in get_versions_string(configuration).split("\n"):
        logger.info(version)
    logger.debug(f"Metric export enabled: {configuration.metrics.enabled}")
    logger.debug(f"Config path: {configs}")
    try:
        if "pytest" not in sys.modules:  # needed for not blocking tests
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
        logger.debug("Configuration loaded")
        runner.run()
    except SystemExit as error:
        logger.debug(f"Exit received with code {error.code}")
        sys.exit(error.code)
    # pylint: disable=broad-except
    except Exception as error:
        if os.environ.get("DEBUG", False):
            logger.exception(f"A critical error occurred: {error}")  # pragma: no cover
        else:
            logger.critical(f"A critical error occurred: {error}")
        if runner:
            runner.stop()
        sys.exit(EXITCODES.ERROR)
    # pylint: enable=broad-except


def signal_handler(__: int, _) -> None:
    """Handle signals for stopping the NG runner."""
    logger.debug("Received termination signal, shutting down NG runner...")
    if Runner.instance:
        Runner.instance.stop()


if __name__ == "__main__":
    cli()
