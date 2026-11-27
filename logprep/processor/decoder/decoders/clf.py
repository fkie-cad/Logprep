"""Decoder for the Common Log Format."""

import re

from logprep.processor.decoder.decoders.common import parse_with_regexes

REGEX_CLF = (
    re.compile(
        r"^"
        r"^(?P<host>[^\s]+)\s+"  # hostname or ip
        r"(?P<ident>[^\s]+)\s+"  # identity RFC 1413
        r"(?P<authuser>[^\s]+)\s+"  # userid requesting the document
        r"\[(?P<timestamp>[^\s]+\s+[^\s]+)\]\s+"  # timestamp strftime format %d/%b/%Y:%H:%M:%S %z
        r'"(?P<request_line>.*)"\s+'  # the requested document
        r"(?P<status>\d{3})\s+"  # the http status returned to the client
        r"(?P<bytes>\d+)\s*"  # content-length of the document transferred
        r"$"
    ),
)


def parse_clf(log_line: str) -> dict[str, str | None]:
    """Parses a common log format line."""
    return parse_with_regexes(log_line, REGEX_CLF)
