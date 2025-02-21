from logprep.abc.output import Output
from logprep.generator.http.batcher import Batcher


class Sender:
    """Manages the Batcher and Output classes"""

    def __init__(self, batcher: Batcher, output: Output, **config):
        self.config = config
        self.batcher = batcher
        self.output = output
        self.target_url = config.get("target_url")
        if not self.target_url:
            raise ValueError("No target_url specified")

    def send_batch(self) -> None:
        """Loads a batch from the message backlog and sends to the endpoint"""
        target_url = self.target_url
        for batch in self.batcher.batches:
            for line in batch:
                # line starts with the target path of the target url
                self.output.store(f"{target_url}/{line}")
                # print(event)
