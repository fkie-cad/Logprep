"""Decoder for logfmt log lines."""

import re

REGEX_LOGFMT_TOKEN = re.compile(r'([\w*?.|#@/-]+)=("[^"]*"|\S*)')


def parse_logfmt(log_line: str) -> dict[str, str]:
    """
    Parses logfmt format.
    Intentionally allows a wide range of key names (even non-identifiers).

    Limitations:
    - Does not support escaped or nested quotes in values
    - Does only parse attributes and ignores the inline message
    """
    tokens = REGEX_LOGFMT_TOKEN.findall(log_line)
    return {key: value.strip('"') for key, value in tokens}
