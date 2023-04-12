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
import codecs
import os
import re

import pkg_resources
from attrs import define, field, validators

DEFAULT_PATTERNS_DIRS = [pkg_resources.resource_filename(__name__, "patterns/ecs-v1")]


@define(slots=True)
class Grok:
    """Grok object"""

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

        for pat_name, regex_str in self.custom_patterns.items():
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
        for key, match in matches.items():
            try:
                if self.type_mapper[key] == "int":
                    matches[key] = int(match)
                if self.type_mapper[key] == "float":
                    matches[key] = float(match)
            except (TypeError, KeyError) as e:
                pass
        return matches

    def set_search_pattern(self, pattern=None):
        if type(pattern) is not str:
            raise ValueError("Please supply a valid pattern")
        self.pattern = pattern
        self._load_search_pattern()

    def _load_search_pattern(self):
        self.type_mapper = {}
        py_regex_pattern = self.pattern
        while True:
            # Finding all types specified in the groks
            m = re.findall(r"%{(\w+):(\w+):(\w+)}", py_regex_pattern)
            for n in m:
                self.type_mapper[n[1]] = n[2]
            # replace %{pattern_name:custom_name} (or %{pattern_name:custom_name:type}
            # with regex and regex group name

            py_regex_pattern = re.sub(
                r"%{(\w+):(\w+)(?::\w+)?}",
                lambda m: "(?P<"
                + m.group(2)
                + ">"
                + self.predefined_patterns[m.group(1)].regex_str
                + ")",
                py_regex_pattern,
            )

            # replace %{pattern_name} with regex
            py_regex_pattern = re.sub(
                r"%{(\w+)}",
                lambda m: "(" + self.predefined_patterns[m.group(1)].regex_str + ")",
                py_regex_pattern,
            )

            if re.search("%{\w+(:\w+)?}", py_regex_pattern) is None:
                break

        self.regex_obj = re.compile(py_regex_pattern)


def _wrap_pattern_name(pat_name):
    return "%{" + pat_name + "}"


def _reload_patterns(patterns_dirs):
    """ """
    all_patterns = {}
    for dir in patterns_dirs:
        for f in os.listdir(dir):
            patterns = _load_patterns_from_file(os.path.join(dir, f))
            all_patterns.update(patterns)

    return all_patterns


def _load_patterns_from_file(file):
    """ """
    patterns = {}
    with codecs.open(file, "r", encoding="utf-8") as f:
        for l in f:
            l = l.strip()
            if l == "" or l.startswith("#"):
                continue

            sep = l.find(" ")
            pat_name = l[:sep]
            regex_str = l[sep:].strip()
            pat = Pattern(pat_name, regex_str)
            patterns[pat.pattern_name] = pat
    return patterns


@define(slots=True)
class Pattern:
    """Pattern implementation"""

    pattern_name: str = field(validator=validators.instance_of(str))
    regex_str: str = field(validator=validators.instance_of(str))
    sub_patterns: dict = field(factory=dict)
