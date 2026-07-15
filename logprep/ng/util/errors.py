import itertools

from logprep.ng.abc.event import LogEvent


class ExtraEventDeliveryFailure(ExceptionGroup):
    """Indicates the failure to store at least a subset of extra events"""

    def __init__(self, message, exceptions):
        super().__init__(message, exceptions)

    @staticmethod
    def from_event(event: LogEvent) -> "ExtraEventDeliveryFailure":
        """Utility method to create a meaningful exception by automatically extracting data"""
        return ExtraEventDeliveryFailure(
            "failed to deliver extra events",
            list(itertools.chain.from_iterable(extra.errors for extra in event.extra_data)),
        )
