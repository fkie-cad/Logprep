import pytest

from logprep.util.grok_pattern_loader import GrokPatternLoader, GrokPatternLoaderError


@pytest.fixture
def grok_pattern_loader():
    return GrokPatternLoader()


class TestGrokPatternLoader:
    def test_load_empty_patterns_file_succeeds(self, grok_pattern_loader):
        expected = dict()
        patterns = grok_pattern_loader.load_from_file(
            "tests/testdata/unit/grok_pattern_loader/patterns_empty.dat"
        )

        assert patterns == expected

    def test_load_single_pattern_succeeds(self, grok_pattern_loader):
        expected = {"TEST": ".*"}
        patterns = grok_pattern_loader.load_from_file(
            "tests/testdata/unit/grok_pattern_loader/patterns_single.dat"
        )

        assert patterns == expected

    def test_load_single_pattern_succeeds_with_comment(self, grok_pattern_loader):
        expected = {"TEST": ".*"}
        patterns = grok_pattern_loader.load_from_file(
            "tests/testdata/unit/grok_pattern_loader/patterns_single_with_comment.dat"
        )

        assert patterns == expected

    def test_load_multiple_patterns_succeeds(self, grok_pattern_loader):
        expected = {"TEST1": ".*", "TEST2": ".*", "TEST3": ".*"}
        patterns = grok_pattern_loader.load_from_file(
            "tests/testdata/unit/grok_pattern_loader/patterns_multiple.dat"
        )

        assert patterns == expected

    def test_load_multiple_patterns_with_blank_lines_succeeds(self, grok_pattern_loader):
        expected = {"TEST1": ".*", "TEST2": ".*", "TEST3": ".*"}
        patterns = grok_pattern_loader.load_from_file(
            "tests/testdata/unit/grok_pattern_loader/patterns_multiple_with_gap.dat"
        )

        assert patterns == expected

    def test_load_patterns_with_duplicate_fails(self, grok_pattern_loader):
        with pytest.raises(GrokPatternLoaderError):
            grok_pattern_loader.load_from_file(
                "tests/testdata/unit/grok_pattern_loader/patterns_duplicate.dat"
            )

    def test_load_multiple_patterns_from_dir_succeeds(self, grok_pattern_loader):
        expected = {"HOLLA": ".*", "Hi": ".*", "SALUT": ".*"}
        patterns = grok_pattern_loader.load_from_dir(
            "tests/testdata/unit/grok_pattern_loader/multiple_patterns/without_duplicates"
        )

        assert patterns == expected

    def test_load_multiple_patterns_from_dir_with_duplicates_across_files_fails(
        self, grok_pattern_loader
    ):
        with pytest.raises(GrokPatternLoaderError):
            grok_pattern_loader.load_from_dir(
                "tests/testdata/unit/grok_pattern_loader/multiple_patterns/with_duplicates"
            )

    def test_load_patterns_from_dir_detects_type(self, grok_pattern_loader):
        assert (
            grok_pattern_loader.load("tests/testdata/unit/grok_pattern_loader/patterns_single.dat")
            is not None
        )
        assert (
            grok_pattern_loader.load(
                "tests/testdata/unit/grok_pattern_loader/multiple_patterns/without_duplicates"
            )
            is not None
        )
