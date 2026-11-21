"""Registry of all available decoders and construction with rule options."""

from functools import partial
from typing import Callable, cast

from logprep.processor.decoder.decoders.base64 import parse_base64
from logprep.processor.decoder.decoders.clf import parse_clf
from logprep.processor.decoder.decoders.common import DecoderFunc
from logprep.processor.decoder.decoders.cri import parse_cri
from logprep.processor.decoder.decoders.decolorize import decolorize
from logprep.processor.decoder.decoders.docker import parse_docker
from logprep.processor.decoder.decoders.json import parse_json
from logprep.processor.decoder.decoders.logfmt import parse_logfmt
from logprep.processor.decoder.decoders.nginx import parse_nginx
from logprep.processor.decoder.decoders.syslog_rfc3164 import parse_syslog_rfc3164
from logprep.processor.decoder.decoders.syslog_rfc3164_local import (
    parse_syslog_rfc3164_local,
)
from logprep.processor.decoder.decoders.syslog_rfc5424 import parse_syslog_rfc5424
from logprep.processor.decoder.decoders.windows_event_log import (
    XmlFieldOverrides,
    parse_windows_event_log,
)
from logprep.util.helper import FieldValue

DECODERS: dict[str, DecoderFunc] = {
    "json": parse_json,
    "base64": parse_base64,
    "clf": parse_clf,
    "nginx": parse_nginx,
    "syslog_rfc5424": parse_syslog_rfc5424,
    "syslog_rfc3164": parse_syslog_rfc3164,
    "syslog_rfc3164_local": parse_syslog_rfc3164_local,
    "logfmt": parse_logfmt,
    "cri": parse_cri,
    "docker": parse_docker,
    "decolorize": decolorize,
    "windows_event_log": parse_windows_event_log,
}


def get_decoder(
    source_format: str, xmlfields: dict[str, XmlFieldOverrides] | None = None
) -> Callable[[str], FieldValue]:
    """Provide the decoder for ``source_format`` with optional rule options applied."""
    decoder = DECODERS[source_format]
    if xmlfields is None:
        return decoder
    if source_format != "windows_event_log":
        raise ValueError("xmlfields is only supported with source_format windows_event_log")
    decoder_with_options = cast(Callable[..., FieldValue], decoder)
    return partial(decoder_with_options, xmlfields=xmlfields)
