import re
from typing import Tuple
from attrs import define, field, validators
from logprep.abc import Getter


class GetterFactory:
    """provides methods to create getters"""

    @classmethod
    def from_string(cls, getter_string: str) -> "Getter":
        """factory method to get a getter

        Parameters
        ----------
        getter_string : str
            a string describing the getter protocol and target informations

        Returns
        -------
        Getter
            the generated getter
        """
        protocol, target = cls._dissect(getter_string)
        if protocol is None:
            protocol = "file"
        return FileGetter(protocol=protocol, target=target)

    @staticmethod
    def _dissect(getter_string: str) -> Tuple[str, str]:
        regexp = r"^((?P<protocol>[^\s]+)://)?(?P<target>.+)"
        matches = re.match(regexp, getter_string)
        return matches.group("protocol"), matches.group("target")


class FileGetter(Getter):
    """FileIO getter"""

    def get(self):
        """opens file and returns its content"""
        return None
