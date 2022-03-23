"""This module contains a delete processor that can be used for testing purposes."""

from logprep.processor.base.processor import BaseProcessor
from logprep.util.processor_stats import ProcessorStats


class Delete(BaseProcessor):
    """A processor that deletes processed log events.

    Notes
    -----
    WARNING: This processor deletes any log event it processes.
    Do not use it for any purpose other than testing.
    You must set the initializer's parameter to 'I really do' to create
    an instance of this processor!

    Parameters
    ----------
    i_really_want_to_delete_all_log_events : str
       Must be set to 'I really do' to avoid to prevent accidental deletion of log events.

    """
    def __init__(self, i_really_want_to_delete_all_log_events: str):
        if i_really_want_to_delete_all_log_events != 'I really do':
            raise ValueError('Read the documentation and pass the correct parameter!')

        self.ps = ProcessorStats()

    def describe(self) -> str:
        return 'DELETE'

    def process(self, event: dict):
        event.clear()
        self.ps.increment_processed_count()
