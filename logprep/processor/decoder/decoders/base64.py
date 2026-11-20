"""Decoder for base64 encoded log lines."""

import base64
import binascii

from logprep.processor.decoder.decoders.common import DecoderError


def parse_base64(log_line: str) -> str:
    """Parses base64 and handles decode errors"""
    try:
        return base64.b64decode(log_line).decode("utf-8")
    except binascii.Error as error:
        raise DecoderError("can't decode base64") from error
