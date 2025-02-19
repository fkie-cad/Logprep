from logprep.abc.output import Output
from logprep.generator.http.batcher import Batcher


class Sender:
    """Manages the Batcher and Output classes"""

    def __init__(
        self,
        batcher: Batcher,
        output: Output,
    ):

        self.batcher = batcher
        self.output = output

    def send_batch(self):
        """Loads a batch from the message backlog and sends to the endpoint"""
        batch = self.batcher.batches()
        self.output.store(batch)
