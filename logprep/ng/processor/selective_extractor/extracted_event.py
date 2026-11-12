"""Concrete Sre Event implementation"""

from logprep.ng.abc.event import ExtraDataEvent


class ExtractedEvent(ExtraDataEvent):
    """An extra event produced by a ``selective_extractor``"""
