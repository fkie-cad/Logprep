"""
This generator will parse example events, manipulate their timestamps and send them to
a defined output
"""

import json
import logging
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from logging import Logger

from logprep.connector.http.output import HttpOutput
from logprep.factory import Factory
from logprep.generator.http.input import Input


class Controller:
    """
    Controls the workflow of the generator by reading inputs, manipulating events and sending them to
    outputs
    """

    def __init__(self, **kwargs):
        self.config = kwargs
        self.thread_count: int = kwargs.get("thread_count")
        self.use_reporter: bool = kwargs.get("report")
        self.log: Logger = logging.getLogger("Generator")
        self.input: Input = Input(self.config)
        output_config = {
            "generator_output": {
                "type": "http_output",
                "user": kwargs.get("user"),
                "password": kwargs.get("password"),
                "events": kwargs.get("events"),
                "target_url": kwargs.get("target_url"),
            }
        }
        self.output: HttpOutput = Factory.create(output_config)

    def run(self):
        """
        Iterate over all event classes, trigger their processing and count the return statistics
        """
        # TODO use a logprep pipeline to handle processing
        self.log.info("Started Data Processing")
        self.input.reformat_dataset()
        run_time_start = time.perf_counter()
        statistics = Counter()
        try:
            self._generate_load(statistics)
        except KeyboardInterrupt:
            self.log.info("Gracefully shutting down...")
        self.input.clean_up_tempdir()
        run_duration = time.perf_counter() - run_time_start
        stats = json.dumps(statistics, sort_keys=True, indent=4, separators=(",", ": "))
        self.log.info("Completed with following http return code statistics: %s", stats)
        self.log.info("Execution time: %f seconds", run_duration)
        return statistics

    def _generate_load(self, statistics):
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            results = executor.map(self.output.store, self.input.load())
            for stats in results:
                statistics.update(stats)
