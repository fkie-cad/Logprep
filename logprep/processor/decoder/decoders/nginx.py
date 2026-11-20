"""Decoder for nginx ingress log lines."""

import re

from logprep.processor.decoder.decoders.common import parse_with_regexes

REGEX_NGINX = (
    re.compile(
        r"^"
        r"(?P<host>[^ ]*) - "
        r"(?P<user>[^ ]*) "
        r"\[(?P<time>[^\]]*)\]\s+"
        r"(?P<code>[^ ]*) "
        r'"(?P<method>\S+)(?: +(?P<path>[^\"]*?)(?: +\S*)?)?"\s+'
        r"(?P<size>[^ ]*)\s+"
        r'"(?P<referer>[^\"]*)"\s+'
        r'"(?P<agent>[^\"]*)"\s+'
        r'"(?P<gzip_ratio>[^\"]*)"'
        r"$"
    ),
    re.compile(
        r"^"
        r"(?P<host>[^ ]*) - "
        r"(?P<user>[^ ]*) "
        r"\[(?P<time>[^\]]*)\]\s+"
        r'"(?P<method>\S+)(?: +(?P<path>[^\"]*?)(?: +\S*)?)?"\s+'
        r"(?P<code>[^ ]*) "
        r"(?P<size>[^ ]*)\s+"
        r'"(?P<referer>[^\"]*)"\s+'
        r'"(?P<agent>[^\"]*)"'
        r"$"
    ),
    re.compile(
        r"^"
        r"(?P<remote>[^ ]*) "
        r"(?P<host>[^ ]*) "
        r"(?P<user>[^ ]*) "
        r"\[(?P<time>[^\]]*)\] "
        r'"(?P<method>\S+)(?: +(?P<path>[^\"]*?)(?: +\S*)?)?" '
        r"(?P<code>[^ ]*) "
        r"(?P<size>[^ ]*)"
        r'(?: "(?P<referer>[^\"]*)" '
        r'"(?P<agent>[^\"]*)")'
        r"$"
    ),
)


def parse_nginx(log_line: str) -> dict[str, str]:
    """Parses an nginx ingress log line."""
    return parse_with_regexes(log_line, REGEX_NGINX)
