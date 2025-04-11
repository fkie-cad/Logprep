import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from itertools import islice


class Input:
    """Input Iterator"""

    _counter = 0

    def get_next(self):
        """retrieves Event"""
        Input._counter += 1
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
        time.sleep(1)
        return f"processed {event}"

    def process_pipeline(self):
        """processes the Pipeline"""
        while True:
            batch = islice(self.input_generator, self.process_count)
            with ProcessPoolExecutor(max_workers=self.process_count) as executor:
                results = executor.map(self.compute, batch)
                yield from results


class Output:
    """output class"""

    def store(self, result):
        """Stores results"""
        print(f"stored {result}")


class Sender:
    """handles pipeline_results into given outputs"""

    def __init__(self, pipeline: Pipeline, output: Output):
        self.pipeline = pipeline
        self.output = output

    def send(self):
        """Send results to output"""
        while True:
            batch = islice(self.pipeline.process_pipeline(), self.pipeline.process_count)
            with ThreadPoolExecutor(max_workers=self.pipeline.process_count) as executor:
                results = executor.map(self.output.store, batch)
                yield from results


class Runner:
    """
    A class to run the pipeline
    """

    def __init__(self, process_count=10):
        self.process_count = process_count
        self.input = Input()
        self.output = Output()
        self.pipeline = Pipeline(self.input)
        self.sender = Sender(self.pipeline, self.output)

    def run(self):
        """Run the pipeline"""
        for _ in self.sender.send():
            pass


if __name__ == "__main__":
    runner = Runner()
    runner.run()
