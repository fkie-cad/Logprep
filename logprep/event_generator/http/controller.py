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

from logprep.event_generator.http.input import Input
from logprep.event_generator.http.output import Output
from logprep.event_generator.http.reporter import Reporter


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
        if self.use_reporter:
            self.reporter = Reporter(args=kwargs)

    def run(self):
        """
        Iterate over all event classes, trigger their processing and count the return statistics
        """
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
        if self.use_reporter:
            self.reporter.set_run_duration(run_duration)
            self.reporter.write_experiment_results()
        stats = json.dumps(statistics, sort_keys=True, indent=4, separators=(",", ": "))
        self.log.info("Completed with following http return code statistics: %s", stats)
        self.log.info("Execution time: %f seconds", run_duration)
        return statistics

    def _generate_load(self, statistics):
        output = Output(self.config)
        if self.thread_count == 1:
            self._generate_with_main_process(output, statistics)
            return
        self._generate_with_multiple_threads(output, statistics)

    def _generate_with_multiple_threads(self, output, statistics):
        with ThreadPoolExecutor(max_workers=self.thread_count) as executor:
            results = executor.map(output.send, self.input.load())
            for stats in results:
                self._update_statistics(statistics, stats)

    def _generate_with_main_process(self, output, statistics):
        for batch in self.input.load():
            stats = output.send(batch)
            self._update_statistics(statistics, stats)

    def _update_statistics(self, statistics, new_statistics):
        statistics.update(new_statistics)
        if self.use_reporter:
            self.reporter.update(new_statistics)
