from logprep.ng.abc.output import Output
from logprep.ng.pipeline import Pipeline


class Sender:
    def __init__(self, pipeline: Pipeline, outputs: list[Output], error_output: Output) -> None:
        self.pipeline = pipeline
        self.outputs = outputs
        self.error_output = error_output
