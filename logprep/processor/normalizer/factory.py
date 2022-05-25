"""This module contains a factory for normalizer processors."""

from logging import Logger

from logprep.processor.base.factory import BaseFactory
from logprep.processor.normalizer.processor import Normalizer


class NormalizerFactory(BaseFactory):
    """Create normalizers."""

    @staticmethod
    def create(name: str, configuration: dict, logger: Logger) -> Normalizer:
        """Create a normalizer."""
        return Normalizer(name=name, configuration=configuration, logger=logger)
