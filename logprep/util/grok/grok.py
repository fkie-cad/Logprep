"""logprep grok implementation
original code from https://github.com/garyelephant/pygrok released under MIT Licence
The MIT License (MIT)

Copyright (c) 2014 

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import re
import string
import sys
from hashlib import md5
from importlib import resources
from itertools import chain
from pathlib import Path
from re import error

import numpy as np
from attrs import define, field, validators

from logprep.util.decorators import timeout

DEFAULT_PATTERNS_DIRS = [str(resources.files(__package__) / "patterns/ecs-v1")]
LOGSTASH_NOTATION = r"(([^\[\]\{\}\.:]*)?(\[[^\[\]\{\}\.:]*\])*)"
GROK = r"%\{" + rf"([A-Z0-9_]*)(:({LOGSTASH_NOTATION}))?(:(int|float))?" + r"\}"
ONIGURUMA = r"\(\?<([^()]*)>\(?(([^()]*|\(([^()]*|\([^()]*\))*\))*)\)?\)"
NON_RESOLVED_ONIGURUMA = r"\(\?<[^md5].*>"
INT_FLOAT = {"int": int, "float": float}


@define(slots=True)
class Grok:
    """Grok object"""

    field_pattern = re.compile(r"\[(.*?)\]")
    grok_pattern = re.compile(GROK)
    oniguruma = re.compile(ONIGURUMA)

    pattern: str = field(validator=validators.instance_of((str, list)))
    custom_patterns_dir: str = field(default="")
    custom_patterns: dict = field(factory=dict)
    fullmatch: bool = field(default=True)
    predefined_patterns: dict = field(init=False, factory=dict, repr=False)
    type_mapper: dict = field(init=False, factory=dict)
    field_mapper: dict = field(init=False, factory=dict)
    regex_obj = field(init=False, default=None)

    def __attrs_post_init__(self):
        self.predefined_patterns = _reload_patterns(DEFAULT_PATTERNS_DIRS)

        custom_pats = {}
        if self.custom_patterns_dir:
            custom_pats = _reload_patterns([self.custom_patterns_dir])

        for pat_name, regex_str in self.custom_patterns.items():  # pylint: disable=no-member
            custom_pats[pat_name] = Pattern(pat_name, regex_str)

        if len(custom_pats) > 0:
            self.predefined_patterns.update(custom_pats)

        self._load_search_pattern()

    @timeout(seconds=1)
    def match(self, text):
        """If text is matched with pattern, return variable names
        specified(%{pattern:variable name}) in pattern and their
        corresponding values. If not matched, return None.
        custom patterns can be passed in by
        custom_patterns(pattern name, pattern regular expression pair)
        or custom_patterns_dir.
        """

        if self.fullmatch:
            match_obj = [regex_pattern.fullmatch(text) for regex_pattern in self.regex_obj]
        else:
            match_obj = [regex_pattern.search(text) for regex_pattern in self.regex_obj]

        match_obj = [match for match in match_obj if match is not None]
        matches = [match.groupdict() for match in match_obj]
        if not matches:
            return {}
        first_match = matches[0]
        if self.type_mapper:
            for key, match in first_match.items():
                type_ = INT_FLOAT.get(self.type_mapper.get(key))
                if type_ is not None and match is not None:
                    first_match[key] = type_(match)
        return {self.field_mapper[field_hash]: value for field_hash, value in first_match.items()}

    def _map_types(self, matches):
        for key, match in matches.items():
            type_ = INT_FLOAT.get(self.type_mapper.get(key))
            if type_ is not None and match is not None:
                matches[key] = type_(match)
        return matches

    def set_search_pattern(self, pattern=None):
        """sets the search pattern"""
        if not isinstance(pattern, str):
            raise ValueError("Please supply a valid pattern")
        self.pattern = pattern
        self._load_search_pattern()

    @staticmethod
    def _to_dundered_field(fields: str) -> str:
        if not "[" in fields:
            return fields
        return re.sub(Grok.field_pattern, r"\g<1>__", fields).strip("__")

    @staticmethod
    def _to_dotted_field(fields: str) -> str:
        if not "__" in fields:
            return fields
        return fields.replace("__", ".")

    def _resolve_grok(self, match: re.Match) -> str:
        name = match.group(1)
        fields = match.group(3)
        pattern = self.predefined_patterns.get(name)
        if pattern is None:
            raise ValueError(f"grok pattern '{name}' not found")
        if fields is None:
            return pattern.regex_str
        type_str = match.group(8)
        dundered_fields = self._to_dundered_field(fields)
        dotted_fields = self._to_dotted_field(dundered_fields)
        fields_hash = f"md5{md5(fields.encode()).hexdigest()}"  # nosemgrep
        if fields_hash in self.field_mapper:
            fields_hash += (
                f"_{''.join(np.random.choice(list(string.ascii_letters), size=10, replace=True))}"
            )
        if type_str is not None:
            self.type_mapper |= {fields_hash: type_str}
        self.field_mapper |= {fields_hash: dotted_fields}
        return rf"(?P<{fields_hash}>" rf"{pattern.regex_str})"

    def _resolve_oniguruma(self, match: re.Match) -> str:
        fields = match.group(1)
        pattern = match.group(2)
        dundered_fields = self._to_dundered_field(fields)
        dotted_fields = self._to_dotted_field(dundered_fields)
        fields_hash = f"md5{md5(fields.encode()).hexdigest()}"  # nosemgrep
        if fields_hash in self.field_mapper:
            fields_hash += (
                f"_{''.join(np.random.choice(list(string.ascii_letters), size=10, replace=True))}"
            )
        self.field_mapper |= {fields_hash: dotted_fields}
        return rf"(?P<{fields_hash}>" rf"{pattern})"

    def _load_search_pattern(self):
        py_regex_pattern = self.pattern
        if isinstance(py_regex_pattern, list):
            self.regex_obj = list(map(self._compile_pattern, py_regex_pattern))
        else:
            self.regex_obj = [self._compile_pattern(py_regex_pattern)]

    def _compile_pattern(self, py_regex_pattern):
        while re.search(Grok.oniguruma, py_regex_pattern):
            py_regex_pattern = re.sub(
                Grok.oniguruma,
                self._resolve_oniguruma,
                py_regex_pattern,
                count=1,
            )
        while re.search(Grok.grok_pattern, py_regex_pattern):
            py_regex_pattern = re.sub(
                Grok.grok_pattern,
                self._resolve_grok,
                py_regex_pattern,
                count=1,
            )
        # Enforce error to be consistent between python versions 3.9 and 3.11
        if re.match(NON_RESOLVED_ONIGURUMA, py_regex_pattern):
            raise error("Not valid oniguruma pattern", pattern=py_regex_pattern)
        return re.compile(py_regex_pattern)


def _reload_patterns(patterns_dirs):
    """ """
    patterns_dirs = [Path(directory) for directory in patterns_dirs]
    patterns_dirs += chain(*[list(directory.rglob("**/*")) for directory in patterns_dirs])
    patterns_dirs = [directory for directory in patterns_dirs if directory.is_dir()]
    all_patterns = {}
    for directory in patterns_dirs:
        pattern_files = [file for file in directory.iterdir() if file.is_file()]
        for pattern_file in pattern_files:
            all_patterns |= _load_patterns_from_file(pattern_file)
    return all_patterns


def _load_patterns_from_file(file):
    patterns = Path(file).read_text(encoding="utf-8").splitlines()
    patterns = [
        line.strip().partition(" ") for line in patterns if not (line.startswith("#") or line == "")
    ]
    return {name: Pattern(name, regex_str.strip()) for name, _, regex_str in patterns}


@define(slots=True)
class Pattern:
    """Pattern implementation"""

    pattern_name: str = field(validator=validators.instance_of(str))
    regex_str: str = field(validator=validators.instance_of(str))
    sub_patterns: dict = field(factory=dict)
