"""Module for conversion of strings into hash strings."""

import hashlib
from abc import ABC, abstractmethod


class Hasher(ABC):
    """Base class to convert strings to hash strings."""

    @staticmethod
    @abstractmethod
    def hash_str(input_string: str, salt: str = "") -> str:
        """Convert a string into a hash string."""


class SHA256Hasher(Hasher):
    """Converts to Sha256 hash."""

    @staticmethod
    def hash_str(input_string: str, salt: str = "") -> str:
        sha256_hash = hashlib.sha256()
        sha256_hash.update(input_string.encode("UTF-8"))
        sha256_hash.update(salt.encode("UTF-8"))
        return sha256_hash.hexdigest()
