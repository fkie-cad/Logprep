"""This module contains a delete processor that can be used for testing purposes."""

from logging import Logger
from logprep.abc import Processor
from logprep.processor.delete.rule import DeleteRule


class Delete(Processor):
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

    __slots__ = []

    rule_class = DeleteRule

    def __init__(self, name: str, configuration: dict, logger: Logger):
        i_really_want_to_delete_all_log_events = configuration.get(
            "i_really_want_to_delete_all_log_events"
        )

        if i_really_want_to_delete_all_log_events != "I really do":
            raise ValueError("Read the documentation and pass the correct parameter!")

        super().__init__(name, configuration, logger)

    def _apply_rules(self, event, rule):
        event.clear()
