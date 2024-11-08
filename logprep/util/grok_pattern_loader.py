"""This module contains a loader for grok patterns."""

from os import walk, path
from typing import Optional

PATTERN_CONVERSION = [("[[:alnum:]]", r"\w")]


class GrokPatternLoaderError(Exception):
    """Base class for GrokPatternLoader related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"GrokPatternLoader: {message}")


class GrokPatternLoader:
    """Used to load grok patterns."""

    @staticmethod
    def load(pattern_path: str) -> Optional[dict]:
        """Load grok patterns from path that might be directory or file.

        Parameters
        ----------
        pattern_path : str
            Path of directory or file containing grok patterns.

        Returns
        -------
        dict
            Dictionary with grok patterns.

        """
        if path.isfile(pattern_path):
            return GrokPatternLoader.load_from_file(pattern_path)
        if path.isdir(pattern_path):
            return GrokPatternLoader.load_from_dir(pattern_path)
        return None

    @staticmethod
    def load_from_file(pattern_path: str) -> dict:
        """Load grok patterns from path to file.

        Parameters
        ----------
        pattern_path : String
            Path of file containing grok patterns.

        Returns
        -------
        grok_pattern_dict: dict
            Dictionary with grok patterns.

        """
        grok_pattern_dict = {}
        with open(pattern_path, "r", encoding="utf8") as pattern_file:
            lines = pattern_file.readlines()
            lines = [line for line in lines if line.strip() and not line.startswith("#")]
            for idx, line in enumerate(lines):
                line = line.rstrip("\n") if idx != len(lines) - 1 else line
                identifier, pattern = line.split(" ", 1)

                if identifier in grok_pattern_dict:
                    raise GrokPatternLoaderError(
                        f"Duplicate pattern definition - Pattern: " f'"{identifier}"'
                    )
                grok_pattern_dict[identifier] = pattern
        return GrokPatternLoader._update_pattern(grok_pattern_dict)

    @staticmethod
    def load_from_dir(pattern_dir_path: str) -> dict:
        """Load grok patterns from path to file.

        Parameters
        ----------
        pattern_dir_path : String
            Path of directory containing grok patterns.

        Returns
        -------
        grok_pattern_dict: dict
            Dictionary with grok patterns.

        """
        grok_pattern_dict = {}
        for root, _, files in walk(pattern_dir_path):
            for file in files:
                new_patterns = GrokPatternLoader.load_from_file(path.join(root, file))
                intersection = set(grok_pattern_dict).intersection(new_patterns)
                if intersection:
                    raise GrokPatternLoaderError(
                        f'Duplicate pattern definition across files - Patterns: "{intersection}"'
                    )
                grok_pattern_dict.update(new_patterns)
        return grok_pattern_dict

    @staticmethod
    def _update_pattern(grok_pattern_dict) -> dict:
        return {
            grok: (
                pattern.replace(non_supported_regex, supported_regex)
                if non_supported_regex in pattern
                else pattern
            )
            for grok, pattern in grok_pattern_dict.items()
            for non_supported_regex, supported_regex in PATTERN_CONVERSION
        }
