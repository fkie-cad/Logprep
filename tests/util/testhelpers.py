from logging import Handler, INFO, getLevelName
from queue import Empty

from pytest import fail


class HandlerStub(Handler):
    def __init__(self):
        self.logs = []
        super().__init__(INFO)

    def emit(self, record):
        self.logs.append(record)

    def clear(self):
        del self.logs[:]

    def get(self, timeout=None):
        return self.logs.pop(0)


##
# Check whether several messages were received.
# The log level must be provided for each message, you may use None to indicate
# that a prefix or message check should be skipped for a log record.
class AssertEmitsLogMessages:
    def __init__(self, log_handler, log_levels, messages=[], prefixes=[], contains=[]):
        self._log_handler_stub = log_handler
        self._expected_levels = log_levels
        self._expected_messages = messages
        self._expected_prefixes = prefixes
        self._expected_contains = contains

        while len(self._expected_messages) < len(self._expected_levels):
            self._expected_messages.append(None)
        while len(self._expected_prefixes) < len(self._expected_levels):
            self._expected_prefixes.append(None)
        while len(self._expected_contains) < len(self._expected_levels):
            self._expected_contains.append(None)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        records = self._retrieve_records()

        if len(records) <= 0:
            fail("Did not emit any log message.")
        elif len(records) < len(self._expected_levels):
            fail(
                "Expected {} log messages but only {} message(s) were emitted.".format(
                    len(self._expected_levels), len(records)
                )
            )

        for offset in range(len(self._expected_levels)):
            if records[offset].levelno != self._expected_levels[offset]:
                fail(
                    "Message {}: Expected log level {}, have {}: {}".format(
                        offset,
                        getLevelName(self._expected_levels[offset]),
                        getLevelName(records[offset].levelno),
                        records[offset].msg,
                    )
                )

            if (not self._expected_messages[offset] is None) and (
                records[offset].msg != self._expected_messages[offset]
            ):
                fail(
                    'Expected message "{}" but got: {}'.format(
                        self._expected_prefixes[offset], records[offset].msg
                    )
                )
            if (not self._expected_prefixes[offset] is None) and (
                records[offset].msg[: len(self._expected_prefixes[offset])]
                != self._expected_prefixes[offset]
            ):
                fail(
                    'Message does not start with prefix "{}": {}'.format(
                        self._expected_prefixes[offset], records[offset].msg
                    )
                )
            if (not self._expected_contains[offset] is None) and (
                not self._expected_contains[offset] in records[offset].msg
            ):
                fail(
                    'Expected message "{}" not found in: {}'.format(
                        self._expected_contains[offset], records[offset].msg
                    )
                )

    def _retrieve_records(self):
        records = []
        while len(records) < len(self._expected_levels):
            try:
                records.append(self._log_handler_stub.get(timeout=0.01))
            except (IndexError, Empty):
                break
        return records


class AssertEmitsLogMessage(AssertEmitsLogMessages):
    def __init__(self, log_handler, log_level, message=None, prefix=None, contains=None):
        super().__init__(log_handler, [log_level], [message], [prefix], [contains])
