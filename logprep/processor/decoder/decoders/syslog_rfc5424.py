"""Decoder for RFC 5424 syslog lines."""

import re

from logprep.processor.decoder.decoders.common import parse_with_regexes

REGEX_ISO8601 = r"\d{4}-[01]\d-[0-3]\dT[0-2]\d:[0-5]\d:[0-5]\d\.\d+([+-][0-2]\d:[0-5]\d|Z)"

REGEX_SYSLOG_RFC5424 = (
    re.compile(
        r"^\<(?P<pri>[0-9]{1,5})\>"
        r"1 "  # the version 1-> rfc5424
        rf"(?P<time>{REGEX_ISO8601}) "
        r"(?P<host>[^ ]+) "
        r"(?P<ident>[^ ]+) "
        r"(?P<pid>[-0-9]+) "
        r"(?P<msgid>[^ ]+) "
        r"(?P<extradata>(\[(.*?)\]|-)) "
        r"(?P<message>.+)$"
    ),
)


def parse_syslog_rfc5424(log_line: str) -> dict[str, str | None]:
    """Parses an RFC 5424 syslog line."""
    return parse_with_regexes(log_line, REGEX_SYSLOG_RFC5424)
