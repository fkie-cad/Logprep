"""implemented decoders"""

import base64
import json
import re
from functools import partial


class DecoderError(Exception):
    """raised if decoding fails"""


def _parse(log_line, regex):
    def _parse(log_line, regex):
        result = re.match(regex, log_line)
        if result is None:
            raise DecoderError("regex does not match")
        return result.groupdict()

    if isinstance(regex, re.Pattern):
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


regex_clf = re.compile(
    (
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
)


regex_nginx = (
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


regex_syslog_rfc3164_local = re.compile(  # local without host
    r"^\<(?P<pri>[0-9]+)\>"
    r"(?P<time>[^ ]* {1,2}[^ ]* [^ ]*) "
    r"(?P<ident>[a-zA-Z0-9_\/\.\-]*)"
    r"(?:\[(?P<pid>[0-9]+)\])?"
    r"(?:[^\:]*\:)? *(?P<message>.*)"
    r"$"
)

regex_syslog_rfc3164 = re.compile(
    r"^\<(?P<pri>[0-9]+)\>"
    r"(?P<time>[^ ]* {1,2}[^ ]* [^ ]*) "
    r"(?P<host>[^ ]*) "
    r"(?P<ident>[a-zA-Z0-9_\/\.\-]*)"
    r"(?:\[(?P<pid>[0-9]+)\])?(?:[^\:]*\:)? "
    r"*(?P<message>.*)"
    r"$"
)

regex_iso8601 = r"\d{4}-[01]\d-[0-3]\dT[0-2]\d:[0-5]\d:[0-5]\d\.\d+([+-][0-2]\d:[0-5]\d|Z)"

regex_syslog_rfc5424 = re.compile(
    r"^\<(?P<pri>[0-9]{1,5})\>"
    r"1 "  # the version 1-> rfc5424
    rf"(?P<time>{regex_iso8601}) "
    r"(?P<host>[^ ]+) "
    r"(?P<ident>[^ ]+) "
    r"(?P<pid>[-0-9]+) "
    r"(?P<msgid>[^ ]+) "
    r"(?P<extradata>(\[(.*?)\]|-)) "
    r"(?P<message>.+)$"
)

token = re.compile(r'^(?P<token>[a-zA-Z0-9]+=(".+"|\S+))')


def parse_logfmt(log_line: str) -> dict[str, str]:
    """parses logfmt format"""
    result: dict[str, str] = {}
    while log_line:
        match_result = token.search(log_line)
        token_result = match_result.groupdict()["token"]
        log_line = log_line.lstrip(token_result + " ")
        key, value = token_result.split("=")
        result |= {key: value.lstrip('"').rstrip('"')}
    return result


DECODERS = {
    "json": json.loads,
    "base64": lambda x: base64.b64decode(x).decode("utf-8"),
    "clf": partial(_parse, regex=regex_clf),
    "nginx": partial(_parse, regex=regex_nginx),
    "syslog_rfc5424": partial(_parse, regex=regex_syslog_rfc5424),
    "syslog_rfc3164": partial(_parse, regex=regex_syslog_rfc3164),
    "syslog_rfc3164_local": partial(_parse, regex=regex_syslog_rfc3164_local),
    "logfmt": parse_logfmt,
}
