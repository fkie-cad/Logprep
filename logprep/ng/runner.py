"""
Runner module
"""

from logprep.util.configuration import Configuration


class Runner:
    """Class responsible for running the log processing pipeline."""

    def __init__(self, configuration: Configuration) -> None:
        self._configuration = configuration
