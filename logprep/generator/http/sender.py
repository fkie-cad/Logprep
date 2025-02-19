from logprep.abc.output import Output
from logprep.generator.http.batcher import Batcher


class Sender:
    """Manages the Batcher and Output classes"""

    def __init__(self, batcher: Batcher, output: Output, **config):
        self.config = config
        self.batcher = batcher
        self.output = output

    def send_batch(self) -> None:
        """Loads a batch from the message backlog and sends to the endpoint"""
        for event in self.batcher.get_batch():
            # self.output.store(event)
            print(event)
