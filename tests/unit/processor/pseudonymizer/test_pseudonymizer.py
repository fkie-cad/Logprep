# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-public-methods
# pylint: disable=line-too-long
import re
from copy import deepcopy

import pytest

from logprep.abc.processor import ProcessorResult
from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.util.pseudo.encrypter import (
    DualPKCS1HybridCTREncrypter,
    DualPKCS1HybridGCMEncrypter,
)
from tests.unit.processor.base import BaseProcessorTestCase

test_cases = [  # testcase, rule, event, expected, regex_mapping
    (
        "simple pseudonymization",
        {
            "filter": "event_id: 1234",
            "pseudonymizer": {"mapping": {"something": "RE_WHOLE_FIELD"}},
            "description": "description content irrelevant for these tests",
        },
        {"event_id": 1234, "something": "something"},
        {
            "event_id": 1234,
            "something": "<pseudonym:8d7e9ea64b00d7df5dd7d4e1c9dde8a0b70815eea27bddb67738502f4ea0d2ee>",
        },
        None,
    ),
    (
        "pseudonymization_of_field_does_not_happen_if_already_pseudonymized",
        {
            "filter": "event_id: 1234",
            "pseudonymizer": {"mapping": {"something": "RE_WHOLE_FIELD"}},
            "description": "description content irrelevant for these tests",
        },
        {
            "event_id": 1234,
            "something": "<pseudonym:8d7e9ea64b00d7df5dd7d4e1c9dde8a0b70815eea27bddb67738502f4ea0d2ee>",
        },
        {
            "event_id": 1234,
            "something": "<pseudonym:8d7e9ea64b00d7df5dd7d4e1c9dde8a0b70815eea27bddb67738502f4ea0d2ee>",
        },
        None,
    ),
    (
        "pseudonymize_two_fields",
        {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymizer": {
                "mapping": {
                    "winlog.event_data.param1": "RE_WHOLE_FIELD",
                    "winlog.event_data.param2": "RE_WHOLE_FIELD",
                }
            },
        },
        {
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "param1": "Pseudonymize me.",
                    "param2": "Pseudonymize me!",
                },
            }
        },
        {
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "param1": "<pseudonym:8f86699f51fc217651b1512f0bc0a2fa7717ffc700fe3e5426229a6ab063b47a>",
                    "param2": "<pseudonym:c40348196f85b761e0633fa568a79c751201a50d63f3a92195985e92cdee2077>",
                },
            }
        },
        None,
    ),
    (
        "match_regex_mapping_with_partial_match",
        {
            "filter": 'winlog.event_id: 789 AND winlog.provider_name: "Test123"',
            "pseudonymizer": {
                "mapping": {"winlog.event_data.param1": "RE_DOMAIN_BACKSLASH_USERNAME"}
            },
        },
        {
            "winlog": {
                "event_id": 789,
                "provider_name": "Test123",
                "event_data": {"param1": r"DOMAIN\pseudonymize me!"},
            }
        },
        {
            "winlog": {
                "event_id": 789,
                "provider_name": "Test123",
                "event_data": {
                    "param1": r"DOMAIN\<pseudonym:fd5ada8080bcb4a2bcf094bb7aaa7cb907fabeebfff8650676676632cdf4ac4c>"
                },
            }
        },
        None,
    ),
    (
        "match replace whole field 1",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {"mapping": {"pseudo_this": "RE_WHOLE_FIELD_CAP"}},
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "to be pseudonymized",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "<pseudonym:08572d32bb4e3aa23a7673fbb633814d62b603bb75b27d8fc9ea4f7b5476478e>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "match replace whole field 2",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {"mapping": {"pseudo_this": "RE_WHOLE_FIELD_EMPTY_CAPS"}},
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "to be pseudonymized",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "<pseudonym:08572d32bb4e3aa23a7673fbb633814d62b603bb75b27d8fc9ea4f7b5476478e>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "match_capture_group_surrounded",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {"mapping": {"pseudo_this": "RE_CAP"}},
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "KEEP_THIS+PSEUDO_THIS+KEEP_THIS",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "KEEP_THIS+"
                "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
                "+KEEP_THIS"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "match_capture_group_right",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {"mapping": {"pseudo_this": "RE_PATTERN_CAP"}},
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "KEEP_THIS+PSEUDO_THIS",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "KEEP_THIS+"
                "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "match_capture_group_left",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {"mapping": {"pseudo_this": "RE_CAP_PATTERN"}},
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "PSEUDO_THIS+KEEP_THIS",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
                "+KEEP_THIS"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "match_two_capture_groups_covering_match",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {"mapping": {"pseudo_this": "RE_TWO_CAPS"}},
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "_PSEUDO_THIS_1__PSEUDO_THIS_2_",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "<pseudonym:c293a7d15377738f5966d78da53f3ba500f3d287a1fdea98bdb225da6212ff68>"
                "<pseudonym:2c868c09bcc9ee59486e915ad2865d33f22b045ea0050215d7f99fd55b12a5d3>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "match_two_capture_groups_with_gap",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {"mapping": {"pseudo_this": "RE_TWO_CAPS_WITH_GAP"}},
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "PSEUDO_THIS+KEEP_THIS+PSEUDO_THIS",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
                "+KEEP_THIS+"
                "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_subdomain",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://www.test.de",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://"
                "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
                ".test.de"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_subdomain_without_scheme",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "www.test.de",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
                ".test.de"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_path",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://test.de/some/path",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://test.de/"
                "<pseudonym:f285389e9dc7921109e18f2f1375b26cb47bbe2981d8399ee7e70c3fd156337f>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_query_values",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://test.de/?a=b&c=d",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://test.de/?a="
                "<pseudonym:4c77fcd97a3d4d98eb062561c37e4ef000f0476bdf153b25ba8031f90ac89877>"
                "&c="
                "<pseudonym:2344d07c391a619a9b16d1e8cfd5252e5aacf93faaf822712948b9a2fd84fce3>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_query_values_substrings",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://test.de/?a=b&c=d&e=bd",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://test.de/?a="
                "<pseudonym:4c77fcd97a3d4d98eb062561c37e4ef000f0476bdf153b25ba8031f90ac89877>"
                "&c="
                "<pseudonym:2344d07c391a619a9b16d1e8cfd5252e5aacf93faaf822712948b9a2fd84fce3>"
                "&e="
                "<pseudonym:49713f9217c2cac56d0e87a6930669f45be876812eff4bd01ec86d6f22578f99>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_subdomain_in_sentence",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "This is https://www.test.de !",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "This is https://"
                "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
                ".test.de !"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_two_identical_urls_subdomain",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://www.test.de https://www.test.de",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://"
                "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
                ".test.de "
                "https://"
                "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
                ".test.de"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_two_different_urls",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://www.other.de/some/path https://www.test.de",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://"
                "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
                ".other.de/"
                "<pseudonym:f285389e9dc7921109e18f2f1375b26cb47bbe2981d8399ee7e70c3fd156337f> "
                "https://"
                "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
                ".test.de"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_username_password",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://user:password@www.test.de",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://"
                "<pseudonym:a204fdad51be9a1e4ee63cea128cc8016226e4459fea2d1ed430c180e6f06359>"
                "@"
                "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
                ".test.de"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_fragment",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://test.de/#test",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://test.de/#"
                "<pseudonym:d95ac3629be3245d3f5e836c059516ad04081d513d2888f546b783d178b02e5a>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_fragment_with_path_and_query",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://test.de/test/?a=b#test",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://test.de/"
                "<pseudonym:25d02f39a74a2bee3e08c5c82577528f70b653f0805ad1c56570829bfb368881>"
                "?a="
                "<pseudonym:4c77fcd97a3d4d98eb062561c37e4ef000f0476bdf153b25ba8031f90ac89877>"
                "#"
                "<pseudonym:d95ac3629be3245d3f5e836c059516ad04081d513d2888f546b783d178b02e5a>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_except_port",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://test.de:123/#test",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://test.de:123/#"
                "<pseudonym:d95ac3629be3245d3f5e836c059516ad04081d513d2888f546b783d178b02e5a>"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_no_valid_html",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "fail://fail.failfailfail https://www.correct.de",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "fail://fail.failfailfail https://"
                "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
                ".correct.de"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_multiple_url_fields",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {
                    "pseudo_this": "RE_ALL_NO_CAP",
                    "and_pseudo_this": "RE_ALL_NO_CAP",
                },
                "url_fields": ["pseudo_this", "and_pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://www.pseudo.this.de",
            "and_pseudo_this": "https://www.pseudo.this.de",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "https://"
                "<pseudonym:f742a956bf2ab54f5e7f9cca7caaa33a1b488f6e907cef147fbfb1a99c8de5b6>"
                ".this.de"
            ),
            "and_pseudo_this": (
                "https://"
                "<pseudonym:f742a956bf2ab54f5e7f9cca7caaa33a1b488f6e907cef147fbfb1a99c8de5b6>"
                ".this.de"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_url_and_cap_groups",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {"pseudo_this": "RE_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": ("SOMETHING PSEUDO_THIS SOMETHING https://www.pseudo.this.de SOMETHING"),
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": (
                "SOMETHING "
                "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
                " SOMETHING https://"
                "<pseudonym:f742a956bf2ab54f5e7f9cca7caaa33a1b488f6e907cef147fbfb1a99c8de5b6>"
                ".this.de SOMETHING"
            ),
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "pseudonymize_list_with_one_element",
        {
            "filter": "pseudo_this",
            "pseudonymizer": {
                "mapping": {
                    "pseudo_this": "RE_WHOLE_FIELD",
                }
            },
        },
        {
            "pseudo_this": ["foo"],
        },
        {
            "pseudo_this": [
                "<pseudonym:e008abcd3e050a10853e0c5f694a10e87d693b8cfdb3457e42376cb06ab218ed>"
            ],
        },
        None,
    ),
    (
        "pseudonymize_list_with_two_equal_element",
        {
            "filter": "pseudo_this",
            "pseudonymizer": {
                "mapping": {
                    "pseudo_this": "RE_WHOLE_FIELD",
                }
            },
        },
        {
            "pseudo_this": ["foo", "foo"],
        },
        {
            "pseudo_this": [
                "<pseudonym:e008abcd3e050a10853e0c5f694a10e87d693b8cfdb3457e42376cb06ab218ed>",
                "<pseudonym:e008abcd3e050a10853e0c5f694a10e87d693b8cfdb3457e42376cb06ab218ed>",
            ],
        },
        None,
    ),
    (
        "pseudonymize_list_with_two_different_element",
        {
            "filter": "pseudo_this",
            "pseudonymizer": {
                "mapping": {
                    "pseudo_this": "RE_WHOLE_FIELD",
                }
            },
        },
        {
            "pseudo_this": ["foo", "bar"],
        },
        {
            "pseudo_this": [
                "<pseudonym:e008abcd3e050a10853e0c5f694a10e87d693b8cfdb3457e42376cb06ab218ed>",
                "<pseudonym:98b611cbecbd6a4533695fad8b40a46210f736ae3ef450fb9c4ab65638397113>",
            ],
        },
        None,
    ),
    (
        "pseudonymize_one_element_from_list_with_two_different_elements",
        {
            "filter": "pseudo_this",
            "pseudonymizer": {
                "mapping": {
                    "pseudo_this": "RE_DOMAIN_BACKSLASH_USERNAME",
                }
            },
        },
        {
            "pseudo_this": ["foo\\test", "bar"],
        },
        {
            "pseudo_this": [
                "foo\\<pseudonym:d95ac3629be3245d3f5e836c059516ad04081d513d2888f546b783d178b02e5a>",
                "bar",
            ],
        },
        None,
    ),
]


class TestPseudonymizer(BaseProcessorTestCase):
    CONFIG = {
        "type": "pseudonymizer",
        "outputs": [{"kafka": "topic"}],
        "pubkey_analyst": "tests/testdata/unit/pseudonymizer/example_analyst_pub.pem",
        "pubkey_depseudo": "tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem",
        "hash_salt": "a_secret_tasty_ingredient",
        "rules": ["tests/testdata/unit/pseudonymizer/rules"],
        "regex_mapping": "tests/testdata/unit/pseudonymizer/regex_mapping.yml",
        "max_cached_pseudonyms": 1000000,
    }

    expected_metrics = [
        "logprep_pseudonymizer_pseudonymized_urls",
        "logprep_pseudonymizer_new_results",
        "logprep_pseudonymizer_cached_results",
        "logprep_pseudonymizer_num_cache_entries",
        "logprep_pseudonymizer_cache_load",
    ]

    def setup_method(self) -> None:
        super().setup_method()
        self.regex_mapping = self.CONFIG.get("regex_mapping")

    @pytest.mark.parametrize(
        "config_change, error, msg",
        [
            ({"outputs": [{"kafka": "topic"}]}, None, None),
            ({"outputs": []}, ValueError, "Length of 'outputs' must be >= 1: 0"),
            (
                {"outputs": [{"kafka": 1}]},
                TypeError,
                "must be <class 'str'>",
            ),
            (
                {"outputs": [{1: "topic"}]},
                TypeError,
                "must be <class 'str'>",
            ),
            (
                {"outputs": [{"kafka": "topic", "opensearch": "index_1"}]},
                ValueError,
                "Length of 'outputs' must be <= 1",
            ),
        ],
    )
    def test_config_validation(self, config_change, error, msg):
        config = deepcopy(self.CONFIG)
        config |= config_change
        if error:
            with pytest.raises(error, match=msg):
                Factory.create({"name": config})
        else:
            Factory.create({"name": config})

    @pytest.mark.parametrize("testcase, rule, event, expected, regex_mapping", test_cases)
    def test_testcases(self, testcase, rule, event, expected, regex_mapping):
        if regex_mapping is not None:
            self.regex_mapping = regex_mapping
        self._load_rule(rule)
        self.object.process(event)
        assert event == expected, testcase

    def _load_rule(self, rule):
        config = deepcopy(self.CONFIG)
        config["regex_mapping"] = self.regex_mapping
        self.object = Factory.create({"pseudonymizer": config})
        super()._load_rule(rule)
        self.object.setup()

    def test_pseudonymize_url_fields_not_in_pseudonymize(self):
        pseudonym = "<pseudonym:d95ac3629be3245d3f5e836c059516ad04081d513d2888f546b783d178b02e5a>"

        url = "https://www.do-not-pseudo.this.de"
        regex_pattern = "RE_WHOLE_FIELD_CAP"
        event = {
            "filter_this": "does_not_matter",
            "do_not_pseudo_this": url,
            "pseudo_this": "test",
        }
        rule = {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {"mapping": {"pseudo_this": regex_pattern}},
            "url_fields": ["do_not_pseudo_this"],
        }
        self.regex_mapping = "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml"
        self._load_rule(rule)
        self.object.process(event)

        assert event["do_not_pseudo_this"] == url
        assert event["pseudo_this"] == pseudonym

    def test_replace_regex_keywords_by_regex_expression_is_idempotent(self):
        rule_dict = {
            "filter": "event_id: 1234",
            "pseudonymizer": {"mapping": {"something": "RE_WHOLE_FIELD"}},
            "description": "description content irrelevant for these tests",
        }
        self._load_rule(rule_dict)  # First call
        expected_pattern = re.compile("(.*)")
        assert self.object._rule_tree.rules[0].pseudonyms == {"something": expected_pattern}
        self.object._replace_regex_keywords_by_regex_expression()  # Second Call
        assert self.object._rule_tree.rules[0].pseudonyms == {"something": expected_pattern}

    def test_pseudonymize_string_adds_pseudonyms(self):
        self.object.result = ProcessorResult(processor_name="test")
        assert self.object._pseudonymize_string("foo").startswith("<pseudonym:")
        assert len(self.object.result.data) == 1

    def test_resolve_from_cache_pseudonym(self):
        rule_dict = {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymizer": {
                "mapping": {
                    "winlog.event_data.param1": "RE_WHOLE_FIELD",
                    "winlog.event_data.param2": "RE_WHOLE_FIELD",
                }
            },
        }
        event = {
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "param1": "Pseudonymize me!",
                    "param2": "Pseudonymize me!",
                },
            }
        }
        self._load_rule(rule_dict)
        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0
        self.object.process(event)
        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 1

    def test_resolve_from_cache_pseudonymize_urls(self):
        rule_dict = {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "mapping": {
                    "pseudo_this": "RE_ALL_NO_CAP",
                    "and_pseudo_this": "RE_ALL_NO_CAP",
                },
                "url_fields": ["pseudo_this", "and_pseudo_this"],
            },
        }
        event = {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://www.pseudo.this.de",
            "and_pseudo_this": "https://www.pseudo.this.de",
        }
        self._load_rule(rule_dict)
        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0
        self.object.process(event)
        # 1 subdomains -> pseudonym_cache, 1 url -> url_cache
        assert self.object.metrics.new_results == 2
        # second url is cached, no string pseudonymization needed
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 2, "same as new results"

    @pytest.mark.parametrize(
        "url, expected",
        [
            (
                "https://www.test.de",
                "https://<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>.test.de",
            ),
            (
                "www.test.de",
                "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>.test.de",
            ),
            (
                "http://www.test.de/this/path",
                "http://<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>.test.de/<pseudonym:bcd18937d7d846fe5489459667e327ef2e11971853b93898e496d5b8be566171>",
            ),
            (
                "https://test.de/?a=b&c=d",
                (
                    "https://test.de/?a="
                    "<pseudonym:4c77fcd97a3d4d98eb062561c37e4ef000f0476bdf153b25ba8031f90ac89877>"
                    "&c="
                    "<pseudonym:2344d07c391a619a9b16d1e8cfd5252e5aacf93faaf822712948b9a2fd84fce3>"
                ),
            ),
            (
                "https://test.de/#test",
                (
                    "https://test.de/#"
                    "<pseudonym:d95ac3629be3245d3f5e836c059516ad04081d513d2888f546b783d178b02e5a>"
                ),
            ),
        ],
    )
    def test_pseudonymize_url(self, url, expected):
        self.object.result = ProcessorResult(processor_name="test")
        assert self.object._pseudonymize_url(url) == expected

    def test_process_returns_extra_output(self):
        rule_dict = {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymizer": {
                "mapping": {
                    "winlog.event_data.param1": "RE_WHOLE_FIELD",
                }
            },
        }
        event = {
            "@timestamp": "custom timestamp",
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "param1": "Pseudonymize me!",
                },
            },
        }
        self._load_rule(rule_dict)  # First call
        extra_output = self.object.process(event)
        assert extra_output.data
        assert isinstance(extra_output.data, list)
        assert isinstance(extra_output, ProcessorResult)
        assert isinstance(extra_output.data[0], tuple)
        assert isinstance(extra_output.data[0][0], dict)
        assert isinstance(extra_output.data[0][1], tuple)
        assert extra_output.data[0][1] == ({"kafka": "topic"},), "Output is set as in CONFIG"
        assert len(extra_output.data) == 1, "Should contain only one pseudonym"
        assert extra_output.data[0][0].get("pseudonym"), "pseudonym is set"
        assert extra_output.data[0][0].get("origin"), "encrypted original is set"
        assert extra_output.data[0][0].get("@timestamp"), "timestamp is set if present in event"

    def test_extra_output_contains_only_one_pseudonym_even_if_pseudonym_appears_multiple_times_in_event(
        self,
    ):
        rule_dict = {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymizer": {
                "mapping": {
                    "winlog.event_data.param1": "RE_WHOLE_FIELD",
                    "winlog.event_data.param2": "RE_WHOLE_FIELD",
                }
            },
        }
        event = {
            "@timestamp": "custom timestamp",
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "param1": "Pseudonymize me - appears twice!",
                    "param2": "Pseudonymize me - appears twice!",
                },
            },
        }
        self._load_rule(rule_dict)  # First call
        extra_output = self.object.process(event)
        assert extra_output
        assert isinstance(extra_output.data, list)
        assert len(extra_output.data[0]) == 2
        assert isinstance(extra_output.data[0], tuple)
        assert isinstance(extra_output.data[0][0], dict)
        assert isinstance(extra_output.data[0][1], tuple)
        assert isinstance(extra_output.data[0][1][0], dict)
        assert extra_output.data[0][1] == ({"kafka": "topic"},), "Output is set as in CONFIG"
        assert (
            len(extra_output.data) == 1
        ), "Should contain only one pseudonym, as the value for both is the same"
        assert extra_output.data[0][0].get("pseudonym"), "pseudonym is set"
        assert extra_output.data[0][0].get("origin"), "encrypted original is set"
        assert extra_output.data[0][0].get("@timestamp"), "timestamp is set if present in event"

    def test_extra_output_contains_different_pseudonyms_for_different_values(self):
        rule_dict = {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymizer": {
                "mapping": {
                    "winlog.event_data.param1": "RE_WHOLE_FIELD",
                    "winlog.event_data.param2": "RE_WHOLE_FIELD",
                }
            },
        }
        event = {
            "@timestamp": "custom timestamp",
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "param1": "Pseudonymize me - first!",
                    "param2": "Pseudonymize me - second!",
                },
            },
        }
        self._load_rule(rule_dict)  # First call
        extra_output = self.object.process(event)
        assert extra_output.data
        assert isinstance(extra_output.data, list)
        assert len(extra_output.data) == 2
        assert isinstance(extra_output.data[0], tuple)  # First item of extra_output
        assert isinstance(extra_output.data[0][0], dict)  # Pseudonym
        assert isinstance(extra_output.data[0][1], tuple)  # Outputs
        assert isinstance(extra_output.data[0][1][0], dict)  # Output
        assert extra_output.data[0][1] == ({"kafka": "topic"},), "Output is set as in CONFIG"
        assert len(extra_output.data) == 2, "Should contain two pseudonyms, for each value one"

        pseudonym_1 = extra_output.data[0][0]
        assert pseudonym_1.get("pseudonym"), "pseudonym is set"
        assert pseudonym_1.get("origin"), "encrypted original is set"
        assert pseudonym_1.get("@timestamp"), "timestamp is set if present in event"

        pseudonym_2 = extra_output.data[1][0]
        assert pseudonym_2.get("pseudonym"), "pseudonym is set"
        assert pseudonym_2.get("origin"), "encrypted original is set"
        assert pseudonym_2.get("@timestamp"), "timestamp is set if present in event"

        assert pseudonym_1.get("pseudonym") != pseudonym_2.get(
            "pseudonym"
        ), "pseudonyms should differ"
        assert pseudonym_1.get("origin") != pseudonym_2.get("origin"), "origins should differ"

    def test_ignores_missing_field_but_add_warning(self):
        rule_dict = {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymizer": {
                "mapping": {
                    "does_not_exists": "RE_WHOLE_FIELD",
                    "winlog.event_data.param2": "RE_WHOLE_FIELD",
                }
            },
        }
        event = {
            "@timestamp": "custom timestamp",
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "param1": "Pseudonymize me!",
                    "param2": "Pseudonymize me!",
                },
            },
        }
        self._load_rule(rule_dict)
        extra_output = self.object.process(event)
        assert extra_output.data[0][0].get("pseudonym"), "pseudonym is set"
        assert "_pseudonymizer_missing_field_warning" in event.get("tags", [])
        assert len(extra_output.data) == 1, "only ONE pseudonym is set"

    @pytest.mark.parametrize(
        "mode, encrypter_class",
        [("CTR", DualPKCS1HybridCTREncrypter), ("GCM", DualPKCS1HybridGCMEncrypter)],
    )
    def test_uses_encrypter(self, mode, encrypter_class):
        config = deepcopy(self.CONFIG)
        config["mode"] = mode
        object_with_encrypter = Factory.create({"pseudonymizer": config})
        assert isinstance(object_with_encrypter._encrypter, encrypter_class)

    def test_setup_raises_invalid_configuration_on_missing_regex_mapping(self):
        rule_dict = {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymizer": {
                "mapping": {
                    "winlog.event_data.param2": "RE_WHOLE_FIELD",
                }
            },
        }
        self._load_rule(rule_dict)
        self.object.rules[0].mapping["winlog.event_data.param2"] = "RE_DOES_NOT_EXIST"
        error_message = (
            r"Regex keyword 'RE_DOES_NOT_EXIST' not found in regex_mapping '.*\/regex_mapping.yml'"
        )
        with pytest.raises(InvalidConfigurationError, match=error_message):
            self.object.setup()

    def test_cache_metrics_updated(self):
        rule_dict = {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymizer": {
                "mapping": {
                    "winlog.event_data.param1": "RE_WHOLE_FIELD",
                }
            },
        }
        event = {
            "@timestamp": "custom timestamp",
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "param1": "Pseudonymize me - appears twice!",
                },
            },
        }
        self._load_rule(rule_dict)

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0

        self.object.process(deepcopy(event))
        self.object.process(deepcopy(event))
        self.object.process(event)
        # because the event is the same, the result is cached
        # metrics are mocked by integers and incremented by cache_info results
        assert self.object.metrics.new_results == 3
        assert self.object.metrics.cached_results == 3
        assert self.object.metrics.num_cache_entries == 3
