"""implemented decoders"""

import base64
import binascii
import re
from functools import partial

import msgspec

from logprep.util.helper import FieldValue

json_decoder = msgspec.json.Decoder()


class DecoderError(Exception):
    """raised if decoding fails"""


def _parse(log_line, regex):
    """this parses a given log_line to a dict via provided regex
    it is really important that you don't use lookahead or lookbehinds
    in the provided regex, because they could break the application by
    recursive expressions in strings
    """

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
        r'"(?P<request_line>.*)"\s+'  # the requested document
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

token_regex = re.compile(r'([a-zA-Z0-9]+)=("[^"]+"|\S+)')


def parse_logfmt(log_line: str) -> dict[str, str]:
    """parses logfmt format"""
    tokens = token_regex.findall(log_line)
    return {key: value.strip('"') for key, value in tokens}


def parse_cri(log_line: str) -> dict[str, str]:
    """parses cri container log format by using only
    string operations"""
    timestamp, _, log_line = log_line.partition(" ")
    stream, _, log_line = log_line.partition(" ")
    flags, _, message = log_line.partition(" ")
    if any((not timestamp, not stream, not flags)):
        raise DecoderError("can't be parsed with cri")
    return {
        "timestamp": timestamp,
        "stream": stream,
        "flags": flags,
        "message": message,
    }


def parse_json(log_line: str) -> dict[str, FieldValue]:
    """parses json and handles decode errors"""
    try:
        return json_decoder.decode(log_line)
    except msgspec.DecodeError as error:
        raise DecoderError("can't decode json") from error


def parse_base64(log_line: str) -> dict[str, FieldValue]:
    """parses base64 and handles decode errors"""
    try:
        return base64.b64decode(log_line).decode("utf-8")
    except binascii.Error as error:
        raise DecoderError("can't decode base64") from error


class DockerLog(msgspec.Struct):
    """Type definition for Docker log line"""

    log: str
    stream: str
    time: str


def parse_docker(log_line: str) -> dict[str, str]:
    """parse docker log lines"""
    try:
        docker_log = msgspec.json.decode(log_line, type=DockerLog)
        return {
            "output": docker_log.log,
            "stream": docker_log.stream,
            "timestamp": docker_log.time,
        }
    except msgspec.DecodeError as error:
        raise DecoderError("can't parse docker log") from error


ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def decolorize(log_line: str) -> str:
    """remove color codes from logs"""
    return ansi_escape.sub("", log_line)


DECODERS = {
    "json": parse_json,
    "base64": parse_base64,
    "clf": partial(_parse, regex=regex_clf),
    "nginx": partial(_parse, regex=regex_nginx),
    "syslog_rfc5424": partial(_parse, regex=regex_syslog_rfc5424),
    "syslog_rfc3164": partial(_parse, regex=regex_syslog_rfc3164),
    "syslog_rfc3164_local": partial(_parse, regex=regex_syslog_rfc3164_local),
    "logfmt": parse_logfmt,
    "cri": parse_cri,
    "docker": parse_docker,
    "decolorize": decolorize,
}
