# pylint: disable=missing-docstring
import re

import pytest

from logprep.util.grok_pattern_loader import GrokPatternLoader


@pytest.fixture(name="pattern")
def grok_pattern():
    loader = GrokPatternLoader()
    return loader.load_from_dir("logprep/util/grok/patterns/ecs-v1")


class TestGrokPattern:
    @pytest.mark.parametrize(
        "test_string, matches",
        (
            ["/usr/http/http-client.log", True],
            ["/usr.log", True],
            ["/usr/./foo.log", True],
            ["/../user.log", True],
            ["/path with spaces/log.file", True],
            ["//path//log.file", True],
            ["///path///log.file", True],
            ["/path///log.file", True],
            ["/path/with/NUMBERS/123/lo3g.file", True],
            ["/path/with/utf8/öüä/log.file", True],
            ["/path///", True],
            ["./user.log", False],
            ["~/user.log", False],
            [",/.", False],
            ["+/.../", False],
            [".", False],
            ["..", False],
            ["something", False],
            ["something with spaces", False],
            [r"\windows\path", False],
            ["\\windows\\path", False],
            [r"\\windows\\\path", False],
        ),
    )
    def test_unixpath_pattern(self, pattern, test_string, matches):
        grok = pattern.get("UNIXPATH")
        if matches:
            assert re.match(grok, test_string)
        else:
            assert not re.match(grok, test_string)
