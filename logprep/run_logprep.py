#!/usr/bin/python3
"""This module can be used to start the logprep."""
import os
from logging import getLogger, Logger, DEBUG, ERROR
from logging.handlers import TimedRotatingFileHandler
from argparse import ArgumentParser
from pathlib import Path
from os.path import dirname, basename
import inspect
from typing import List, Optional

import sys

from logprep.runner import Runner
from logprep.util.schema_and_rule_checker import SchemaAndRuleChecker
from logprep.util.configuration import Configuration
from logprep.util.rule_dry_runner import DryRunner
from logprep.util.auto_rule_tester import AutoRuleTester
from logprep.util.aggregating_logger import AggregatingLogger
from logprep.processor.base.rule import Rule
from logprep.processor.processor_factory import ProcessorFactory

from logprep.util.time_measurement import TimeMeasurement
from logprep.util.processor_stats import StatsClassesController
from logprep.util.prometheus_exporter import PrometheusStatsExporter

DEFAULT_LOCATION_CONFIG = "/etc/logprep/pipeline.yml"
getLogger("filelock").setLevel(ERROR)


def _get_status_logger(config: dict, application_logger: Logger) -> List:
    status_logger_cfg = config.get("status_logger", dict())
    logging_targets = status_logger_cfg.get("targets", [])

    if not logging_targets:
        logging_targets.append({"file": {}})

    status_logger = []
    for target in logging_targets:
        if "file" in target.keys():
            file_config = target.get("file")
            logger = getLogger("Logprep-JSON-File-Logger")
            logger.handlers = []

            log_path = file_config.get("path", "./logprep-status.jsonl")
            Path(dirname(log_path)).mkdir(parents=True, exist_ok=True)
            interval = file_config.get("rollover_interval", 60 * 60 * 24)
            backup_count = file_config.get("backup_count", 10)
            logger.addHandler(
                TimedRotatingFileHandler(
                    log_path, when="S", interval=interval, backupCount=backup_count
                )
            )
            status_logger.append(logger)

        if "prometheus" in target.keys():
            multi_processing_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "")
            if multi_processing_dir == "":
                application_logger.warning(
                    "Prometheus Exporter was is deactivated because the"
                    "mandatory environment variable "
                    "'PROMETHEUS_MULTIPROC_DIR' is missing."
                )
            else:
                prometheus_exporter = PrometheusStatsExporter(status_logger_cfg, application_logger)
                prometheus_exporter.run()
                status_logger.append(prometheus_exporter)

    return status_logger


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


def _run_logprep(arguments, logger: Logger, status_logger: Optional[List]):
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


def get_processor_type_and_rule_class() -> dict:
    return {
        basename(Path(inspect.getfile(rule_class)).parent): rule_class
        for rule_class in Rule.__subclasses__()
    }


def main():
    """Start the logprep runner."""
    args = _parse_arguments()
    config = Configuration().create_from_yaml(args.config)
    config.verify(getLogger("Temporary Logger"))

    for plugin_dir in config.get("plugin_directories", []):
        sys.path.insert(0, plugin_dir)
        ProcessorFactory.load_plugins(plugin_dir)

    AggregatingLogger.setup(config, logger_disabled=args.disable_logging)
    logger = AggregatingLogger.create("Logprep")

    status_logger = None
    if not args.disable_logging:
        status_logger = _get_status_logger(config, logger)

    TimeMeasurement.TIME_MEASUREMENT_ENABLED = config.get("measure_time", False)
    StatsClassesController.ENABLED = config.get("status_logger", dict()).get("enabled", True)

    if logger.isEnabledFor(DEBUG):
        logger.debug(f"Time measurement enabled: {TimeMeasurement.TIME_MEASUREMENT_ENABLED}")
        logger.debug(f"Status logger enabled: {StatsClassesController.ENABLED}")
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
            exit(1)
        elif not args.auto_test:
            exit(0)

    if args.auto_test:
        TimeMeasurement.TIME_MEASUREMENT_ENABLED = False
        StatsClassesController.ENABLED = False
        auto_rule_tester = AutoRuleTester(args.config)
        auto_rule_tester.run()
    elif args.dry_run:
        json_input = True if args.dry_run_input_type == "json" else False
        dry_runner = DryRunner(
            args.dry_run, args.config, args.dry_run_full_output, json_input, logger
        )
        dry_runner.run()
    else:
        _run_logprep(args, logger, status_logger)


if __name__ == "__main__":
    main()
