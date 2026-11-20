"""Decoder that strips ANSI color codes from log lines."""

import re

ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def decolorize(log_line: str) -> str:
    """Removes color codes from logs"""
    return ANSI_ESCAPE.sub("", log_line)
