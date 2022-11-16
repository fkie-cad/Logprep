#!/usr/bin/python3
"""This module can be used to start the logprep."""
# pylint: disable=logging-fstring-interpolation
import inspect
import logging
import os
import sys
from argparse import ArgumentParser
from logging import getLogger, Logger, DEBUG, ERROR
from os.path import basename
from pathlib import Path

from colorama import Fore

from logprep._version import get_versions
from logprep.processor.base.rule import Rule
from logprep.runner import Runner
from logprep.util.aggregating_logger import AggregatingLogger
from logprep.util.auto_rule_tester import AutoRuleTester
from logprep.util.configuration import Configuration, InvalidConfigurationError
from logprep.util.helper import print_fcolor
from logprep.util.rule_dry_runner import DryRunner
from logprep.util.schema_and_rule_checker import SchemaAndRuleChecker
from logprep.util.time_measurement import TimeMeasurement

logging.captureWarnings(True)

DEFAULT_LOCATION_CONFIG = "/etc/logprep/pipeline.yml"
getLogger("filelock").setLevel(ERROR)
getLogger("urllib3.connectionpool").setLevel(ERROR)
getLogger("elasticsearch").setLevel(ERROR)


def _parse_arguments():
    argument_parser = ArgumentParser()
    argument_parser.add_argument(
        "--version",
        help="print the current version and exit",
        action="store_true",
    )
    argument_parser.add_argument(
        "config",
        nargs="?",
        help=f"Path to configuration file, if not given then "
        f"the default path '{DEFAULT_LOCATION_CONFIG}' is used",
        default=DEFAULT_LOCATION_CONFIG,
    )
    argument_parser.add_argument("--disable-logging", help="Disable logging", action="store_true")
    argument_parser.add_argument(
        "--validate-rules",
        help="Validate Labeler Rules (if well-formed" " and valid against given schema)",
        action="store_true",
    )
    argument_parser.add_argument(
        "--verify-config",
        help="Verify the configuration file",
        action="store_true",
    )
    argument_parser.add_argument(
        "--dry-run",
        help="Dry run pipeline with events in given " "path and print results",
        metavar="PATH_TO_JSON_LINE_FILE_WITH_EVENTS",
    )
    argument_parser.add_argument(
        "--dry-run-input-type",
        choices=["json", "jsonl"],
        default="json",
        help="Specify input type for dry-run",
    )
    argument_parser.add_argument(
        "--dry-run-full-output",
        help="Print full dry-run output, including " "all extra output",
        action="store_true",
    )
    argument_parser.add_argument("--auto-test", help="Run rule-tests", action="store_true")
    arguments = argument_parser.parse_args()

    requires_dry_run = arguments.dry_run_full_output or arguments.dry_run_input_type == "jsonl"
    if requires_dry_run and not arguments.dry_run:
        argument_parser.error("--dry-run-input-type and --dry-run-full-output require --dry-run")

    return arguments


def _run_logprep(arguments, logger: Logger):
    runner = None
    try:
        runner = Runner.get_runner()
        runner.set_logger(logger)
        runner.load_configuration(arguments.config)
        if logger.isEnabledFor(DEBUG):  # pragma: no cover
            logger.debug("Configuration loaded")
        runner.start()
    # pylint: disable=broad-except
    except BaseException as error:
        logger.critical(f"A critical error occurred: {error}")
        if runner:
            runner.stop()
    # pylint: enable=broad-except


def get_processor_type_and_rule_class() -> dict:  # pylint: disable=missing-docstring
    return {
        basename(Path(inspect.getfile(rule_class)).parent): rule_class
        for rule_class in Rule.__subclasses__()
    }


def print_version_and_exit(args):
    """
    Prints the version and exists. If a configuration was found then it's version
    is printed as well
    """
    versions = get_versions()
    print(f"logprep version: \t\t {versions['version']}")
    if args.config and os.path.isfile(args.config):
        config = Configuration().create_from_yaml(args.config)
        config_version = f"{config.get('version', 'unset')}, {os.path.abspath(args.config)}"
    else:
        config_version = f"no configuration found in '{os.path.abspath(args.config)}'"
    print(f"configuration version: \t {config_version}")
    sys.exit(0)


def main():
    """Start the logprep runner."""
    args = _parse_arguments()

    if args.version:
        print_version_and_exit(args)

    if not os.path.isfile(args.config):
        print(f"The given config file does not exist: {args.config}", file=sys.stderr)
        print(
            "Create the configuration or change the path. Use '--help' for more information.",
            file=sys.stderr,
        )
        sys.exit(1)

    config = Configuration().create_from_yaml(args.config)
    try:
        AggregatingLogger.setup(config, logger_disabled=args.disable_logging)
        logger = AggregatingLogger.create("Logprep")
    except BaseException as error:  # pylint: disable=broad-except
        getLogger("Logprep").exception(error)
        sys.exit(1)

    try:
        if args.validate_rules or args.auto_test:
            config.verify_pipeline_only(logger)
        else:
            config.verify(logger)
    except InvalidConfigurationError:
        sys.exit(1)
    except BaseException as error:  # pylint: disable=broad-except
        logger.exception(error)
        sys.exit(1)

    measure_time_config = config.get("metrics", {}).get("measure_time", {})
    TimeMeasurement.TIME_MEASUREMENT_ENABLED = measure_time_config.get("enabled", False)
    TimeMeasurement.APPEND_TO_EVENT = measure_time_config.get("append_to_event", False)

    if logger.isEnabledFor(DEBUG):  # pragma: no cover
        logger.debug(f'Metric export enabled: {config.get("metrics", {}).get("enabled", False)}')
        logger.debug(f"Time measurement enabled: {TimeMeasurement.TIME_MEASUREMENT_ENABLED}")
        logger.debug(f"Config path: {args.config}")
    if args.validate_rules or args.auto_test:
        type_rule_map = get_processor_type_and_rule_class()
        rules_valid = []
        for processor_type, rule_class in type_rule_map.items():
            rules_valid.append(
                SchemaAndRuleChecker().validate_rules(
                    args.config, processor_type, rule_class, logger
                )
            )
        if not all(rules_valid):
            sys.exit(1)
        if not args.auto_test:
            sys.exit(0)

    if args.auto_test:
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = False
        auto_rule_tester = AutoRuleTester(args.config)
        auto_rule_tester.run()
    elif args.dry_run:
        json_input = args.dry_run_input_type == "json"
        dry_runner = DryRunner(
            args.dry_run, args.config, args.dry_run_full_output, json_input, logger
        )
        dry_runner.run()
    elif args.verify_config:
        print_fcolor(Fore.GREEN, "The verification of the configuration was successful")
    else:
        _run_logprep(args, logger)


if __name__ == "__main__":
    main()
