"""Utility decoders for common log formats used by Logprep.

This module provides small, focused decoding helpers that convert raw
log lines into Python structures (typically dicts) for downstream
processors. Each decoder wraps parsing logic and maps decoding errors to
``DecoderError`` so callers can handle failures uniformly.

Notes
- The internal ``_parse`` helper performs regex matching and supports
    a single ``re.Pattern`` or an iterable of patterns. Avoid lookahead
    and lookbehind in supplied regexes to prevent pathological cases.
- ``parse_json`` uses ``msgspec`` for fast, strict JSON decoding and
    converts decode errors to ``DecoderError``.
- ``decolorize`` strips ANSI escape sequences from log lines.
"""

import base64
import binascii
import re
from functools import partial
from typing import Dict, Generic, Iterable, Protocol, TypeVar, runtime_checkable

import msgspec

from logprep.util.helper import FieldValue

JSON_DECODER = msgspec.json.Decoder()


class DecoderError(Exception):
    """Raised if decoding fails"""


DecoderFuncResult_co = TypeVar("DecoderFuncResult_co", bound=FieldValue, covariant=True)


@runtime_checkable
class DecoderFunc(Generic[DecoderFuncResult_co], Protocol):
    """
    Covariant function type for decoding string values
    into concrete variants of `FieldValue`
    """

    def __call__(self, log_line: str) -> DecoderFuncResult_co: ...


def _parse(log_line: str, regexes: Iterable[re.Pattern]) -> dict[str, str]:
    """This parses a given log_line to a dict via provided regex
    it is really important that you don't use lookahead or lookbehinds
    in the provided regex, because they could break the application by
    recursive expressions in strings
    """

    result = None
    for regex in regexes:
        result = re.match(regex, log_line)
        if result is not None:
            return result.groupdict()
    raise DecoderError("no regex matches")


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

REGEX_SYSLOG_RFC3164 = (
    re.compile(
        r"^\<(?P<pri>[0-9]+)\>"
        r"(?P<time>[^ ]* {1,2}[^ ]* [^ ]*) "
        r"(?P<host>[^ ]*) "
        r"(?P<ident>[a-zA-Z0-9_\/\.\-]*)"
        r"(?:\[(?P<pid>[0-9]+)\])?(?:[^\:]*\:)? "
        r"*(?P<message>.*)"
        r"$"
    ),
)

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


REGEX_LOGFMT_TOKEN = re.compile(r'([a-zA-Z0-9]+)=("[^"]+"|\S+)')


def parse_logfmt(log_line: str) -> dict[str, str]:
    """Parses logfmt format"""
    tokens = REGEX_LOGFMT_TOKEN.findall(log_line)
    return {key: value.strip('"') for key, value in tokens}


def parse_cri(log_line: str) -> dict[str, str]:
    """Parses cri container log format by using only
    string operations"""
    try:
        timestamp, stream, flags, message = log_line.split(" ", maxsplit=3)
    except ValueError as error:
        raise DecoderError("can't be parsed with cri") from error
    return {
        "timestamp": timestamp,
        "stream": stream,
        "flags": flags,
        "message": message,
    }


def parse_json(log_line: str) -> dict[str, FieldValue]:
    """Parses json and handles decode errors"""
    try:
        return JSON_DECODER.decode(log_line)
    except msgspec.DecodeError as error:
        raise DecoderError("can't decode json") from error


def parse_base64(log_line: str) -> str:
    """Parses base64 and handles decode errors"""
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
    """Parses docker log lines"""
    try:
        docker_log = msgspec.json.decode(log_line, type=DockerLog)
        return {
            "output": docker_log.log,
            "stream": docker_log.stream,
            "timestamp": docker_log.time,
        }
    except msgspec.DecodeError as error:
        raise DecoderError("can't parse docker log") from error


ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def decolorize(log_line: str) -> str:
    """Removes color codes from logs"""
    return ANSI_ESCAPE.sub("", log_line)


DECODERS: Dict[str, DecoderFunc] = {
    "json": parse_json,
    "base64": parse_base64,
    "clf": partial(_parse, regexes=REGEX_CLF),
    "nginx": partial(_parse, regexes=REGEX_NGINX),
    "syslog_rfc5424": partial(_parse, regexes=REGEX_SYSLOG_RFC5424),
    "syslog_rfc3164": partial(_parse, regexes=REGEX_SYSLOG_RFC3164),
    "syslog_rfc3164_local": partial(_parse, regexes=REGEX_SYSLOG_RFC3164_LOCAL),
    "logfmt": parse_logfmt,
    "cri": parse_cri,
    "docker": parse_docker,
    "decolorize": decolorize,
}
