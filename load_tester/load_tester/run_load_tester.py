"""Main module for the load-tester"""
from argparse import ArgumentParser
from multiprocessing import Manager
from pathlib import Path

from load_tester.configuration import load_config
from load_tester.logger import create_logger
from load_tester.process_runner import run_processes
from load_tester.util import print_results, print_startup_info


def _parse_arguments():
    argument_parser = ArgumentParser()
    argument_parser.add_argument("config", help="Path to configuration file", type=Path)
    argument_parser.add_argument("-f", "--file", help="Path to file with documents", type=Path)
    arguments = argument_parser.parse_args()

    return arguments


def main():
    """Start function for the load-tester"""
    args = _parse_arguments()
    config = load_config(args.config, args.file)
    logger = create_logger(config.logging_level)

    print_startup_info(config, logger)

    manager = Manager()
    shared_dict = manager.dict()

    run_processes(config, shared_dict, logger)
    print_results(config, logger, shared_dict)


if __name__ == "__main__":
    main()
