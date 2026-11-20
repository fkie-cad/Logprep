"""Decoder for Docker JSON log lines."""

import msgspec

from logprep.processor.decoder.decoders.common import DecoderError


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
