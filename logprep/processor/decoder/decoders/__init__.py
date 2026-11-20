"""Decoders for common log formats used by Logprep.

Every decoder lives in its own module and converts a raw log line into a
Python structure (typically a dict). Decoding errors are mapped to
``DecoderError`` so the decoder processor can handle failures uniformly.
The ``DECODERS`` registry maps the configured ``source_format`` to the
corresponding decoder function.
"""

from logprep.processor.decoder.decoders.base64 import parse_base64
from logprep.processor.decoder.decoders.clf import REGEX_CLF, parse_clf
from logprep.processor.decoder.decoders.common import (
    DecoderError,
    DecoderFunc,
    DecoderFuncResult_co,
    parse_with_regexes,
)
from logprep.processor.decoder.decoders.cri import parse_cri
from logprep.processor.decoder.decoders.decolorize import ANSI_ESCAPE, decolorize
from logprep.processor.decoder.decoders.docker import DockerLog, parse_docker
from logprep.processor.decoder.decoders.json import JSON_DECODER, parse_json
from logprep.processor.decoder.decoders.logfmt import REGEX_LOGFMT_TOKEN, parse_logfmt
from logprep.processor.decoder.decoders.nginx import REGEX_NGINX, parse_nginx
from logprep.processor.decoder.decoders.registry import DECODERS, get_decoder
from logprep.processor.decoder.decoders.syslog_rfc3164 import (
    REGEX_SYSLOG_RFC3164,
    parse_syslog_rfc3164,
)
from logprep.processor.decoder.decoders.syslog_rfc3164_local import (
    REGEX_SYSLOG_RFC3164_LOCAL,
    parse_syslog_rfc3164_local,
)
from logprep.processor.decoder.decoders.syslog_rfc5424 import (
    REGEX_ISO8601,
    REGEX_SYSLOG_RFC5424,
    parse_syslog_rfc5424,
)
from logprep.processor.decoder.decoders.windows_event_log import (
    DATA_SECTIONS,
    MAX_XML_DEPTH,
    SECTIONS,
    XML_FIELDS,
    XmlFieldDefinition,
    parse_windows_event_log,
    validate_fields,
)

__all__ = [
    "ANSI_ESCAPE",
    "DATA_SECTIONS",
    "DECODERS",
    "DecoderError",
    "DecoderFunc",
    "DecoderFuncResult_co",
    "DockerLog",
    "JSON_DECODER",
    "MAX_XML_DEPTH",
    "REGEX_CLF",
    "REGEX_ISO8601",
    "REGEX_LOGFMT_TOKEN",
    "REGEX_NGINX",
    "REGEX_SYSLOG_RFC3164",
    "REGEX_SYSLOG_RFC3164_LOCAL",
    "REGEX_SYSLOG_RFC5424",
    "SECTIONS",
    "XML_FIELDS",
    "XmlFieldDefinition",
    "decolorize",
    "get_decoder",
    "parse_base64",
    "parse_clf",
    "parse_cri",
    "parse_docker",
    "parse_json",
    "parse_logfmt",
    "parse_nginx",
    "parse_syslog_rfc3164",
    "parse_syslog_rfc3164_local",
    "parse_syslog_rfc5424",
    "parse_with_regexes",
    "parse_windows_event_log",
    "validate_fields",
]
