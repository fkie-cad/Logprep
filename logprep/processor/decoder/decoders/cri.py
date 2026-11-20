"""Decoder for CRI container log lines."""

from logprep.processor.decoder.decoders.common import DecoderError


def parse_cri(log_line: str) -> dict[str, str]:
    """Parses cri container log format by using only string operations"""
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
