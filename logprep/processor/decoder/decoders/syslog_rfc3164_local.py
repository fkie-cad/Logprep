"""Decoder for RFC 3164 syslog lines without a host field."""

import re

from logprep.processor.decoder.decoders.common import parse_with_regexes

REGEX_SYSLOG_RFC3164_LOCAL = (
    re.compile(  # local without host
        r"^\<(?P<pri>[0-9]+)\>"
        r"(?P<time>[^ ]* {1,2}[^ ]* [^ ]*) "
        r"(?P<ident>[a-zA-Z0-9_\/\.\-]*)"
        r"(?:\[(?P<pid>[0-9]+)\])?"
        r"(?:[^\:]*\:)? *(?P<message>.*)"
        r"$"
    ),
)


def parse_syslog_rfc3164_local(log_line: str) -> dict[str, str]:
    """Parses an RFC 3164 syslog line without a host field."""
    return parse_with_regexes(log_line, REGEX_SYSLOG_RFC3164_LOCAL)
