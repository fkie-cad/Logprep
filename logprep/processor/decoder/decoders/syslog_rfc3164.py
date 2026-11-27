"""Decoders for RFC 3164 syslog lines, with and without a host field."""

import re

from logprep.processor.decoder.decoders.common import parse_with_regexes

_PRI = r"\<(?P<pri>[0-9]+)\>"
_TIME = r"(?P<time>[^ ]+ {1,2}[^ ]+ [^ ]+)"
_HOST = r"(?P<host>[^ ]+)"
_TAG_PID = r"(?:(?P<ident>[a-zA-Z0-9_\/\.\-]+)(?:\[(?P<pid>[0-9]+)\])?: *)?"
_MESSAGE = r"(?P<message>.*)"

# Example: <86>Nov 27 09:14:03 webserver01 sshd[4721]: Accepted publickey for ...
# <PRI>TIMESTAMP HOSTNAME TAG[PID]: CONTENT
# <PRI>TIMESTAMP HOSTNAME TAG: CONTENT
# <PRI>TIMESTAMP HOSTNAME CONTENT
REGEX_SYSLOG_RFC3164 = (re.compile(rf"^{_PRI}{_TIME} +{_HOST} +{_TAG_PID}{_MESSAGE}$"),)
REGEX_SYSLOG_RFC3164_LOCAL = (re.compile(rf"^{_PRI}{_TIME} +{_TAG_PID}{_MESSAGE}$"),)


def parse_syslog_rfc3164(log_line: str) -> dict[str, str | None]:
    """Parses an RFC 3164 syslog line."""
    return parse_with_regexes(log_line, REGEX_SYSLOG_RFC3164)


def parse_syslog_rfc3164_local(log_line: str) -> dict[str, str | None]:
    """Parses an RFC 3164 syslog line without a host field."""
    return parse_with_regexes(log_line, REGEX_SYSLOG_RFC3164_LOCAL)
