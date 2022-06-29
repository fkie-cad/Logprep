#!/usr/bin/python3
"""This module can be used to start the logprep."""
import inspect
import os
import sys
from argparse import ArgumentParser
from logging import getLogger, Logger, DEBUG, ERROR
from logging.handlers import TimedRotatingFileHandler
from os.path import dirname, basename
from pathlib import Path
from typing import Optional

from colorama import Fore

from logprep.framework.metrics.metric_targets import MetricFileTarget, PrometheusMetricTarget
from logprep.processor.base.rule import Rule
from logprep.runner import Runner
from logprep.util.aggregating_logger import AggregatingLogger
from logprep.util.auto_rule_tester import AutoRuleTester
from logprep.util.configuration import Configuration, InvalidConfigurationError
from logprep.util.helper import print_fcolor
from logprep.framework.metrics.metric import MetricTargets
from logprep.util.rule_dry_runner import DryRunner
from logprep.util.schema_and_rule_checker import SchemaAndRuleChecker
from logprep.util.time_measurement import TimeMeasurement

DEFAULT_LOCATION_CONFIG = "/etc/logprep/pipeline.yml"
getLogger("filelock").setLevel(ERROR)


def _get_metric_targets(config: dict, logger: Logger) -> MetricTargets:
    metric_configs = config.get("metrics", {})

    if not metric_configs.get("enabled", False):
        return MetricTargets(None, None)

    target_configs = metric_configs.get("targets", [])
    file_exporter = None
    prometheus_exporter = None
    for target in target_configs:
        if "file" in target.keys():
            file_exporter = MetricFileTarget.create(target.get("file"))
        if "prometheus" in target.keys():
            prometheus_exporter = PrometheusMetricTarget.create(metric_configs, logger)
    return MetricTargets(file_exporter, prometheus_exporter)


def _parse_arguments():
    argument_parser = ArgumentParser()
    argument_parser.add_argument(
        "config", help="Path to configuration file", default=DEFAULT_LOCATION_CONFIG
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


def _run_logprep(arguments, logger: Logger, status_logger: Optional[MetricTargets]):
    runner = None
    try:
        runner = Runner.get_runner()
        runner.set_logger(logger, status_logger)
        runner.load_configuration(arguments.config)
        if logger.isEnabledFor(DEBUG):
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


def main():
    """Start the logprep runner."""
    args = _parse_arguments()
    config = Configuration().create_from_yaml(args.config)

    try:
        AggregatingLogger.setup(config, logger_disabled=args.disable_logging)
        logger = AggregatingLogger.create("Logprep")
    except BaseException as error:
        getLogger("Logprep").exception(error)
        sys.exit(1)

    try:
        if args.validate_rules or args.auto_test:
            config.verify_pipeline_only(logger)
        else:
            config.verify(logger)
    except InvalidConfigurationError:
        sys.exit(1)
    except BaseException as error:
        logger.exception(error)
        sys.exit(1)

    metric_targets = None
    if not args.disable_logging:
        metric_targets = _get_metric_targets(config, logger)

    measure_time_config = config.get("metrics", {}).get("measure_time", {})
    TimeMeasurement.TIME_MEASUREMENT_ENABLED = measure_time_config.get("enabled", False)
    TimeMeasurement.APPEND_TO_EVENT = measure_time_config.get("append_to_event", False)

    if logger.isEnabledFor(DEBUG):
        logger.debug("Metric export enabled: %s", config.get("metrics", {}).get("enabled", False))
        logger.debug("Time measurement enabled: %s", TimeMeasurement.TIME_MEASUREMENT_ENABLED)
        logger.debug("Config path: %s", args.config)

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
        _run_logprep(args, logger, metric_targets)


if __name__ == "__main__":
    main()
