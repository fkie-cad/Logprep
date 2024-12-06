# pylint: disable=missing-module-docstring


from random import choice
from string import ascii_lowercase

import pytest

from logprep.util.url import extract_urls


class TestExtractUrls:

    @pytest.mark.parametrize(
        "field_value, expected",
        [
            ("https://www.test.de", ["https://www.test.de"]),
            (
                "https://www.test.de https://www.test.de",
                ["https://www.test.de", "https://www.test.de"],
            ),
            (
                "some text https://www.test.de other text https://www.test.de",
                ["https://www.test.de", "https://www.test.de"],
            ),
            (
                "some text https://www.test.de, other text https://www.test.de",
                ["https://www.test.de", "https://www.test.de"],
            ),
            (
                "some text www.test.de other text https://www.test.de",
                ["www.test.de", "https://www.test.de"],
            ),
            (
                "some text https://www.test.de:30080 other trailing text",
                ["https://www.test.de:30080"],
            ),
            (
                "some text https://www.test.de:30080/path?query=4#fragment other trailing text",
                ["https://www.test.de:30080/path?query=4#fragment"],
            ),
            (
                "www.test.de",
                ["www.test.de"],
            ),
            (
                "https://stackoverflow.com/questions/520031/whats-the-cleanest-way-to-extract-urls-from-a-string-using-python",
                [
                    "https://stackoverflow.com/questions/520031/whats-the-cleanest-way-to-extract-urls-from-a-string-using-python"
                ],
            ),
            (
                "https://stackoverflow.com/questions/520031/whats-the-cleanest-way-to-extract-urls-from-a-string-using-python",
                [
                    "https://stackoverflow.com/questions/520031/whats-the-cleanest-way-to-extract-urls-from-a-string-using-python"
                ],
            ),
            ("fail://www.test.de", []),
            ("https://test.de/#test", ["https://test.de/#test"]),
            ("https://test.de/path/#test", ["https://test.de/path/#test"]),
            ("https://test.de/path/?query=1#test", ["https://test.de/path/?query=1#test"]),
            ("http://", []),
        ],
    )
    def test_extract_urls(self, field_value, expected):
        assert extract_urls(field_value) == expected

    def test_extract_urls_random_max_large_string(self):
        n = 300
        random_max_large_string = "".join(choice(ascii_lowercase) for _ in range(n))
        assert extract_urls(f"http://{random_max_large_string}.com") == []

    def test_extract_urls_with_large_domain_label(self):
        domain_label = "a" * 64
        assert extract_urls(f"http://www.{domain_label}.com") == []
