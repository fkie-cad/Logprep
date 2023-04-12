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
from pathlib import Path

import pkg_resources
from attrs import define, field, validators

from logprep.util.helper import add_field_to

DEFAULT_PATTERNS_DIRS = [pkg_resources.resource_filename(__name__, "patterns/ecs-v1")]

LOGSTASH_NOTATION = r"(([^\[\]\{\}\.:]*)?(\[[^\[\]\{\}\.:]*\])*)"
GROK = r"%\{" + rf"([A-Z0-9_]*)(:({LOGSTASH_NOTATION}))?(:(int|float))?" + r"\}"


@define(slots=True)
class Grok:
    """Grok object"""

    field_pattern = re.compile(r"\[(.*?)\]")
    grok_pattern = re.compile(GROK)

    pattern: str = field(validator=validators.instance_of(str))
    custom_patterns_dir: str = field(default="")
    custom_patterns: dict = field(factory=dict)
    fullmatch: bool = field(default=True)
    predefined_patterns: dict = field(init=False, factory=dict)
    type_mapper: dict = field(init=False, factory=dict)
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

    def match(self, text):
        """If text is matched with pattern, return variable names specified(%{pattern:variable name})
        in pattern and their corresponding values.If not matched, return None.
        custom patterns can be passed in by custom_patterns(pattern name, pattern regular expression pair)
        or custom_patterns_dir.
        """

        match_obj = None
        if self.fullmatch:
            match_obj = self.regex_obj.fullmatch(text)
        else:
            match_obj = self.regex_obj.search(text)

        if match_obj is None:
            return None
        matches = match_obj.groupdict()
        if self.type_mapper:
            for key, match in matches.items():
                try:
                    if self.type_mapper[key] == "int":
                        matches[key] = int(match)
                    if self.type_mapper[key] == "float":
                        matches[key] = float(match)
                except (TypeError, KeyError):
                    pass
        result = {}
        for key, match in matches.items():
            add_field_to(result, key.replace("__", "."), match, False, True)
        return result

    def set_search_pattern(self, pattern=None):
        if not isinstance(pattern, str):
            raise ValueError("Please supply a valid pattern")
        self.pattern = pattern
        self._load_search_pattern()

    @staticmethod
    def _to_dundered_field(fields: str) -> str:
        if not "[" in fields:
            return fields
        return re.sub(Grok.field_pattern, r"\g<1>__", fields).strip("__")

    def _get_regex(self, match: re.Match) -> str:
        name = match.group(1)
        fields = match.group(3)
        if fields is None:
            return self.predefined_patterns.get(name).regex_str
        type_str = match.group(8)
        if type_str is not None:
            self.type_mapper |= {fields: type_str}
        return (
            rf"(?P<{self._to_dundered_field(fields)}>"
            rf"{self.predefined_patterns.get(name).regex_str})"
        )

    def _load_search_pattern(self):
        py_regex_pattern = self.pattern
        while re.search(Grok.grok_pattern, py_regex_pattern):
            py_regex_pattern = re.sub(
                Grok.grok_pattern,
                self._get_regex,
                py_regex_pattern,
                count=1,
            )

        self.regex_obj = re.compile(py_regex_pattern)


def _reload_patterns(patterns_dirs):
    """ """
    patterns_dirs = [Path(directory) for directory in patterns_dirs]
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
