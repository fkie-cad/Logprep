"""implemented decoders"""

import base64
import json
import re

from logprep.util.helper import FieldValue


class DecoderError(Exception):
    """raised if decoding fails"""


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
    result = re.match(regex, log_line)
    if result is None:
        raise DecoderError
    return result.groupdict()


DECODERS = {
    "json": json.loads,
    "base64": lambda x: base64.b64decode(x).decode("utf-8"),
    "clf": parse_clf,
}
