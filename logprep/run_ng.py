# pylint: disable=logging-fstring-interpolation
"""This module can be used to start the logprep."""

import asyncio
import logging
import signal
import sys
import warnings
from functools import partial
from multiprocessing import set_start_method

import click
import uvloop

from logprep.ng.runner import Runner
from logprep.ng.util.async_helpers import asyncio_exception_handler
from logprep.ng.util.configuration import Configuration, InvalidConfigurationError
from logprep.ng.util.defaults import DEFAULT_LOG_CONFIG
from logprep.registry import Registry
from logprep.util.defaults import EXITCODES
from logprep.util.helper import get_versions_string
from logprep.util.tag_yaml_loader import init_yaml_loader_tags

EPILOG_STR = "Check out our docs at https://logprep.readthedocs.io/en/latest/"
init_yaml_loader_tags("safe", "rt")


logger = logging.getLogger("root")


def _print_version(config: "Configuration") -> None:
    print(get_versions_string(config))
    sys.exit(EXITCODES.SUCCESS)


async def _get_configuration(config_paths: tuple[str]) -> Configuration:
    try:
        config = await Configuration.from_sources(config_paths)
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

    logging.captureWarnings(True)
    logging.config.dictConfig(DEFAULT_LOG_CONFIG)
    warnings.simplefilter("always", DeprecationWarning)

    set_start_method("fork", force=True)
    Registry.set_ng_active(True)


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

    async def _run():
        if (task := asyncio.current_task()) is not None:
            task.set_name("root")
        configuration = await _get_configuration(configs)
        runner = Runner(configuration)
        with runner.with_configured_logging():
            if version:
                _print_version(configuration)
            for v in get_versions_string(configuration).split("\n"):
                logger.info(v)
            logger.debug(f"Metric export enabled: {configuration.metrics.enabled}")
            logger.debug(f"Config path: {configs}")
            try:
                if "pytest" not in sys.modules:
                    # needed for not blocking tests
                    loop = asyncio.get_running_loop()
                    loop.add_signal_handler(signal.SIGTERM, runner.stop)
                    loop.add_signal_handler(signal.SIGINT, runner.stop)
                logger.debug("Configuration loaded")
                await runner.run()
            except SystemExit as error:
                logger.debug(f"Exit received with code {error.code}")
                sys.exit(error.code)
            # pylint: disable=broad-except
            except ExceptionGroup as error_group:
                logger.exception(f"Multiple errors occurred: {error_group}")
            except Exception as error:
                logger.exception(f"A critical error occurred: {error}")

                if runner:
                    runner.stop()
                sys.exit(EXITCODES.ERROR)
            # pylint: enable=broad-except

    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
        handler = partial(asyncio_exception_handler, logger=logger)
        loop = runner.get_loop()
        loop.set_exception_handler(handler)
        runner.run(_run())


if __name__ == "__main__":
    cli()
