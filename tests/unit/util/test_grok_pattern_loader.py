# pylint: disable=missing-docstring
from unittest import mock

import pytest

from logprep.util.grok_pattern_loader import GrokPatternLoader, GrokPatternLoaderError


@pytest.fixture(name="pattern_loader")
def grok_pattern_loader():
    return GrokPatternLoader()


class TestGrokPatternLoader:
    def test_load_empty_patterns_file_succeeds(self, pattern_loader):
        expected = {}
        patterns = pattern_loader.load_from_file(
            "tests/testdata/unit/grok_pattern_loader/patterns_empty.dat"
        )
        assert patterns == expected

    def test_load_single_pattern_succeeds(self, pattern_loader):
        expected = {"TEST": ".*"}
        patterns = pattern_loader.load_from_file(
            "tests/testdata/unit/grok_pattern_loader/patterns_single.dat"
        )
        assert patterns == expected

    def test_load_single_pattern_succeeds_with_comment(self, pattern_loader):
        expected = {"TEST": ".*"}
        patterns = pattern_loader.load_from_file(
            "tests/testdata/unit/grok_pattern_loader/patterns_single_with_comment.dat"
        )
        assert patterns == expected

    def test_load_multiple_patterns_succeeds(self, pattern_loader):
        expected = {"TEST1": ".*", "TEST2": ".*", "TEST3": ".*"}
        patterns = pattern_loader.load_from_file(
            "tests/testdata/unit/grok_pattern_loader/patterns_multiple.dat"
        )
        assert patterns == expected

    def test_load_multiple_patterns_with_blank_lines_succeeds(self, pattern_loader):
        expected = {"TEST1": ".*", "TEST2": ".*", "TEST3": ".*"}
        patterns = pattern_loader.load_from_file(
            "tests/testdata/unit/grok_pattern_loader/patterns_multiple_with_gap.dat"
        )
        assert patterns == expected

    def test_load_patterns_with_duplicate_fails(self, pattern_loader):
        with pytest.raises(GrokPatternLoaderError):
            pattern_loader.load_from_file(
                "tests/testdata/unit/grok_pattern_loader/patterns_duplicate.dat"
            )

    def test_load_multiple_patterns_from_dir_succeeds(self, pattern_loader):
        expected = {"HOLLA": ".*", "Hi": ".*", "SALUT": ".*"}
        patterns = pattern_loader.load_from_dir(
            "tests/testdata/unit/grok_pattern_loader/multiple_patterns/without_duplicates"
        )
        assert patterns == expected

    def test_load_multiple_patterns_from_dir_with_duplicates_across_files_fails(
        self, pattern_loader
    ):
        with pytest.raises(GrokPatternLoaderError):
            pattern_loader.load_from_dir(
                "tests/testdata/unit/grok_pattern_loader/multiple_patterns/with_duplicates"
            )

    def test_load_patterns_from_dir_detects_type(self, pattern_loader):
        assert (
            pattern_loader.load("tests/testdata/unit/grok_pattern_loader/patterns_single.dat")
            is not None
        )
        assert (
            pattern_loader.load(
                "tests/testdata/unit/grok_pattern_loader/multiple_patterns/without_duplicates"
            )
            is not None
        )

    @mock.patch(
        "logprep.util.grok_pattern_loader.PATTERN_CONVERSION",
        [
            ("[[:alnum:]]", r"\w"),
        ],
    )
    @pytest.mark.parametrize(
        ["given_pattern", "expected_pattern"],
        [
            (".*", ".*"),
            ("[a-zA-Z]", "[a-zA-Z]"),
            ("(/[[[:alnum:]]_%!$@:.,+~-]*)+", r"(/[\w_%!$@:.,+~-]*)+"),
            ("(/[[[:anum:]]_%!$@:.,+~-]*)+", "(/[[[:anum:]]_%!$@:.,+~-]*)+"),
            ("(/[_%!$@:.,+~-]*)+", r"(/[_%!$@:.,+~-]*)+"),
            (r"(/[[[:alnum:]]\w_%!$@:.,+~-]*)+", r"(/[\w\w_%!$@:.,+~-]*)+"),
        ],
    )
    def test_update_pattern(self, pattern_loader, given_pattern, expected_pattern):
        given = {"pattern": given_pattern}
        expected = {"pattern": expected_pattern}
        updated_pattern = pattern_loader._update_pattern(given)  # pylint: disable=protected-access
        assert updated_pattern == expected
