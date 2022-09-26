"""This module contains exceptions related to the normalizer processor."""

from typing import List


class NormalizerError(BaseException):
    """Base class for Normalizer related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"Normalizer ({name}): {message}")


class DuplicationError(NormalizerError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and were not overwritten by the Normalizer: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)
