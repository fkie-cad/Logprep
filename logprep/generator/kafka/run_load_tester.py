"""Main module for the load-tester"""

from multiprocessing import Manager
from pathlib import Path

from logprep.generator.kafka.configuration import load_config
from logprep.generator.kafka.logger import create_logger
from logprep.generator.kafka.process_runner import run_processes
from logprep.generator.kafka.util import print_results, print_startup_info


class LoadTester:
    """Load Tester to generate events from kafka to kafka."""

    def __init__(self, config, file):
        self.config = Path(config)
        self.file = Path(file) if file is not None else None

    def run(self):
        """Start function for the load-tester"""
        config = load_config(self.config, self.file)
        logger = create_logger(config.logging_level)

        print_startup_info(config, logger)

        manager = Manager()
        shared_dict = manager.dict()

        run_processes(config, shared_dict, logger)
        print_results(config, logger, shared_dict)
