"""Shared types and helpers for the individual decoder modules."""

import re
from typing import Generic, Protocol, Sequence, TypeVar, runtime_checkable

from logprep.util.helper import FieldValue


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


def parse_with_regexes(log_line: str, regexes: Sequence[re.Pattern]) -> dict[str, str]:
    """Parse a log line with the first matching regex.

    It is really important that you don't use lookahead or lookbehinds in the
    provided regexes, because they could break the application by recursive
    expressions in strings.
    """
    for regex in regexes:
        result = re.match(regex, log_line)
        if result is not None:
            return result.groupdict()
    raise DecoderError("no regex matches")
