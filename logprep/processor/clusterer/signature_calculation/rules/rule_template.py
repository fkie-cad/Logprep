"""Module for rule (Signature-Phase) template definition"""

from types import SimpleNamespace


class SignatureRule(SimpleNamespace):
    """Template for signature definition."""

    pattern = r""
    repl = r""
    description = ""
