"""Decoder for JSON log lines."""

import msgspec

from logprep.processor.decoder.decoders.common import DecoderError
from logprep.util.helper import FieldValue

JSON_DECODER = msgspec.json.Decoder()


def parse_json(log_line: str) -> dict[str, FieldValue]:
    """Parses json and handles decode errors"""
    try:
        return JSON_DECODER.decode(log_line)
    except msgspec.DecodeError as error:
        raise DecoderError("can't decode json") from error
