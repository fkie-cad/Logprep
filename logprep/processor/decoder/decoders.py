"""implemented decoders"""

import base64
import json
import re

from logprep.util.helper import FieldValue


class DecoderError(Exception):
    """raised if decoding fails"""


def _parse(log_line, regex):
    def _parse(log_line, regex):
        result = re.match(regex, log_line)
        if result is None:
            raise DecoderError("regex does not match")
        return result.groupdict()

    if isinstance(regex, str):
        return _parse(log_line, regex)

    result = None
    for r in regex:
        try:
            result = _parse(log_line, r)
            break
        except DecoderError:
            pass
    else:
        raise DecoderError("no regex matches")
    return result


def parse_clf(log_line: str) -> dict[str, FieldValue]:
    """parses clf
    see: https://en.wikipedia.org/wiki/Common_Log_Format
    """
    regex = (
        r"^"
        r"^(?P<host>[^\s]+)\s+"  # hostname or ip
        r"(?P<ident>[^\s]+)\s+"  # identity RFC 1413
        r"(?P<authuser>[^\s]+)\s+"  # userid requesting the document
        r"\[(?P<timestamp>[^\s]+\s+[^\s]+)\]\s+"  # timestamp in strftime format %d/%b/%Y:%H:%M:%S %z
        r'"(?P<request_line>.*)"\s+'  # the requestd document
        r"(?P<status>\d{3})\s+"  # the http status returned to the client
        r"(?P<bytes>\d+)\s*"  # content-length of the document transferred
        r"$"
    )
    return _parse(log_line, regex)


def parse_nginx(log_line: str) -> dict[str, FieldValue]:
    """parses nginx log format"""
    regex = (
        (
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
        (
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
        (
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
    return _parse(log_line, regex)


def parse_syslog_rfc3164(log_line: str) -> dict[str, FieldValue]:
    """parses syslog rfc3164 and rfc5424"""
    regex = (
        (
            r"^\<(?P<pri>[0-9]+)\>"
            r"(?P<time>[^ ]* {1,2}[^ ]* [^ ]*) "
            r"(?P<host>[^ ]*) "
            r"(?P<ident>[a-zA-Z0-9_\/\.\-]*)"
            r"(?:\[(?P<pid>[0-9]+)\])?(?:[^\:]*\:)? "
            r"*(?P<message>.*)"
            r"$"
        ),
    )
    return _parse(log_line, regex)


DECODERS = {
    "json": json.loads,
    "base64": lambda x: base64.b64decode(x).decode("utf-8"),
    "clf": parse_clf,
    "nginx": parse_nginx,
    "syslog_rfc3164": parse_syslog_rfc3164,
}
