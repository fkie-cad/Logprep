# pylint: disable=missing-module-docstring


from random import choice
from string import ascii_lowercase

import pytest

from logprep.util.url.url import Domain, extract_urls


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


class TestDomain:

    @pytest.mark.parametrize(
        "domain, expected_subdomain, expected_domain, expected_suffix, expected_fqdn",
        [
            ("www.thedomain.com", "www", "thedomain", "com", "www.thedomain.com"),
            ("www.thedomain.co", "www", "thedomain", "co", "www.thedomain.co"),
            ("www.thedomain.com.ua", "www", "thedomain", "com.ua", "www.thedomain.com.ua"),
            ("www.thedomain.co.uk", "www", "thedomain", "co.uk", "www.thedomain.co.uk"),
            ("save.edu.ao", "", "save", "edu.ao", "save.edu.ao"),
            ("thedomain.sport", "", "thedomain", "sport", "thedomain.sport"),
            ("thedomain.联通", "", "thedomain", "联通", "thedomain.联通"),
            ("www.thedomain.foobar", "", "", "", ""),
        ],
    )
    def test_get_labels_from_domain(
        self, domain, expected_subdomain, expected_domain, expected_suffix, expected_fqdn
    ):
        assert Domain(domain).suffix == expected_suffix
        assert Domain(domain).domain == expected_domain
        assert Domain(domain).subdomain == expected_subdomain
        assert Domain(domain).fqdn == expected_fqdn
