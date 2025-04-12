import json
import tempfile
import timeit
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from itertools import islice, product
from pathlib import Path

from logprep.factory import Factory
from logprep.util.time import TimeParser


class Input:
    """Input Iterator"""

    _counter = 0

    _elements = 10

    def __init__(self, events: int):
        self._elements = events

    def get_next(self):
        """retrieves Event"""
        self._counter += 1
        if self._counter >= self._elements:
            raise RuntimeError("No more events")
        return f"event {Input._counter}"

    def __next__(self):
        return self.get_next()

    def __iter__(self):
        return self

    __call__ = __next__


class Pipeline:
    """Pipeline class to process events in batches"""

    process_count = 5

    def __init__(self, input_generator):
        self.input_generator = input_generator

    def __next__(self):
        next(self.input_generator)

    def __iter__(self):
        return self

    def compute(self, event):
        """Does some computational work"""
        result = 0
        for i in range(1000):
            for j in range(1000):
                result += i * j
        return {
            "processed": event,
            "@timestamp": TimeParser.from_timestamp(TimeParser.now().timestamp()).isoformat(),
            "result": result,
        }

    def process_pipeline(self):
        """processes the Pipeline"""
        while True:
            batch = islice(self.input_generator, self.process_count)
            results = map(self.compute, batch)
            yield from results


class PipelineMP(Pipeline):
    """Pipeline class to process events in batches"""

    def process_pipeline(self):
        """processes the Pipeline"""
        while True:
            batch = islice(self.input_generator, self.process_count)
            with ProcessPoolExecutor(max_workers=self.process_count) as executor:
                results = executor.map(self.compute, batch)
                yield from results


class Output:
    """output class"""

    def __init__(self):
        self.tempdir = tempfile.gettempdir()

    def store(self, result: dict):
        """Stores results"""
        with open(self.tempdir + "/result.txt", "w") as file:
            for i in range(1000):
                result.update({"line": i})
                json_line = json.dumps(result)
                file.write(json_line)
        # print(f"stored {result}")

    def shut_down(self):
        Path(self.tempdir + "/result.txt").unlink(missing_ok=True)


class Sender:
    """handles pipeline_results into given outputs"""

    def __init__(self, pipeline: Pipeline, output: Output):
        self.pipeline = pipeline
        self.output = output

    def send(self):
        """Send results to output"""
        while True:
            batch = islice(self.pipeline.process_pipeline(), self.pipeline.process_count)
            results = map(self.output.store, batch)
            yield from results


class SenderMT(Sender):
    """handles pipeline_results into given outputs"""

    def send(self):
        """Send results to output"""
        while True:
            batch = islice(self.pipeline.process_pipeline(), self.pipeline.process_count)
            with ThreadPoolExecutor(max_workers=self.pipeline.process_count) as executor:
                results = executor.map(self.output.store, batch)
                yield from results


class SenderMP(Sender):
    """handles pipeline_results into given outputs"""

    def send(self):
        """Send results to output"""
        while True:
            batch = islice(self.pipeline.process_pipeline(), self.pipeline.process_count)
            with ProcessPoolExecutor(max_workers=self.pipeline.process_count) as executor:
                results = executor.map(self.output.store, batch)
                yield from results


class Runner:
    """
    A class to run the pipeline
    """

    output_config = {
        "type": "opensearchng_output",
        "hosts": ["127.0.0.1:9200"],
        "default_index": "processed",
        "default_op_type": "create",
        "message_backlog_size": 500,
        "timeout": 10000,
        "flush_timeout": 60,
        "user": "admin",
        "secret": "admin",
        "desired_cluster_status": ["green", "yellow"],
    }

    def __init__(self, pipeline_class, sender_class, events=100, process_count=10):
        self.process_count = process_count
        self.input = Input(events)
        # self.output = Output()
        self.output = Factory.create({"opensearch": self.output_config})
        # print(self.output._config.default_index)
        self.pipeline = pipeline_class(self.input)
        self.sender = sender_class(self.pipeline, self.output)

    def run(self):
        """Run the pipeline"""
        try:
            for _ in self.sender.send():
                pass
        except RuntimeError as error:
            self.output.shut_down()
            # print(error)


if __name__ == "__main__":
    # runner = Runner(1000)
    # runner.run()
    pipelines = (Pipeline, PipelineMP)
    senders = (Sender, SenderMT)
    for prod in product(pipelines, senders):
        pipeline, sender = prod
        print(f"{pipeline.__name__}, {sender.__name__}: ", end="")
        spend_time = timeit.Timer(Runner(pipeline, sender, 10_000).run).timeit(number=1)
        print(f"{spend_time=} seconds")
