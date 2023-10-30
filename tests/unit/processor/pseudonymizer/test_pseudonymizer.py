# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-public-methods
import datetime
import logging
import re
import time
from copy import deepcopy
from pathlib import Path

import pytest

from logprep.factory import Factory
from tests.unit.processor.base import BaseProcessorTestCase

CAP_GROUP_REGEX_MAPPING = "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml"

CACHE_MAX_TIMEDELTA = datetime.timedelta(milliseconds=100)

REL_TLD_LIST_PATH = "tests/testdata/mock_external/tld_list.dat"

TLD_LIST = f"file://{Path().absolute().joinpath(REL_TLD_LIST_PATH).as_posix()}"


test_cases = [  # testcase, rule, event, expected, regex_mapping
    (
        "simple pseudonymization",
        {
            "filter": "event_id: 1234",
            "pseudonymizer": {"pseudonyms": {"something": "RE_WHOLE_FIELD"}},
            "description": "description content irrelevant for these tests",
        },
        {"event_id": 1234, "something": "something"},
        {
            "event_id": 1234,
            "something": "<pseudonym:8d7e9ea64b00d7df5dd7d4e1c9dde8a0b70815eea27bddb67738502f4ea0d2ee>",
        },
        None,
    ),
    # (
    #     "pseudonymization_of_field_does_not_happen_if_already_pseudonymized",
    #     {
    #         "filter": "event_id: 1234",
    #         "pseudonymizer": {"pseudonyms": {"something": "RE_WHOLE_FIELD"}},
    #         "description": "description content irrelevant for these tests",
    #     },
    #     {
    #         "event_id": 1234,
    #         "something": "<pseudonym:8d7e9ea64b00d7df5dd7d4e1c9dde8a0b70815eea27bddb67738502f4ea0d2ee>",
    #     },
    #     {
    #         "event_id": 1234,
    #         "something": "<pseudonym:8d7e9ea64b00d7df5dd7d4e1c9dde8a0b70815eea27bddb67738502f4ea0d2ee>",
    #     },
    #     None,
    # ),
    (
        "pseudonymize_two_fields",
        {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymizer": {
                "pseudonyms": {
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
                "pseudonyms": {"winlog.event_data.param1": "RE_DOMAIN_BACKSLASH_USERNAME"}
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
            "pseudonymizer": {"pseudonyms": {"pseudo_this": "RE_WHOLE_FIELD_CAP"}},
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
            "pseudonymizer": {"pseudonyms": {"pseudo_this": "RE_WHOLE_FIELD_EMPTY_CAPS"}},
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
            "pseudonymizer": {"pseudonyms": {"pseudo_this": "RE_CAP"}},
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
            "pseudonymizer": {"pseudonyms": {"pseudo_this": "RE_PATTERN_CAP"}},
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
            "pseudonymizer": {"pseudonyms": {"pseudo_this": "RE_CAP_PATTERN"}},
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
            "pseudonymizer": {"pseudonyms": {"pseudo_this": "RE_TWO_CAPS"}},
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
            "pseudonymizer": {"pseudonyms": {"pseudo_this": "RE_TWO_CAPS_WITH_GAP"}},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
        "pseudonymize_url_query",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
        "pseudonymize_url_query_substrings",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
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
                "pseudonyms": {
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
                "pseudonyms": {"pseudo_this": "RE_CAP"},
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
                "pseudonyms": {
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
                "pseudonyms": {
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
                "pseudonyms": {
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
                "pseudonyms": {
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

failure_test_cases = [  # testcase, rule, event, expected
    (
        "do_not_pseudonymize_url",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://test.de",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "https://test.de",
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
    (
        "do_not_pseudonymize_url_without_scheme",
        {
            "filter": "filter_this: does_not_matter",
            "pseudonymizer": {
                "pseudonyms": {"pseudo_this": "RE_ALL_NO_CAP"},
                "url_fields": ["pseudo_this"],
            },
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "test.de",
        },
        {
            "filter_this": "does_not_matter",
            "pseudo_this": "test.de",
        },
        "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml",
    ),
]


class TestPseudonymizer(BaseProcessorTestCase):
    CONFIG = {
        "type": "pseudonymizer",
        "outputs": [{"kafka": "topic"}],
        "pubkey_analyst": "tests/testdata/unit/pseudonymizer/example_analyst_pub.pem",
        "pubkey_depseudo": "tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem",
        "hash_salt": "a_secret_tasty_ingredient",
        "specific_rules": ["tests/testdata/unit/pseudonymizer/rules/specific/"],
        "generic_rules": ["tests/testdata/unit/pseudonymizer/rules/generic/"],
        "regex_mapping": "tests/testdata/unit/pseudonymizer/rules/regex_mapping.yml",
        "max_cached_pseudonyms": 1000000,
        "max_caching_days": 1,
    }

    expected_metrics = [
        "logprep_pseudonymizer_pseudonymized_urls",
    ]

    def setup_method(self) -> None:
        super().setup_method()
        self.regex_mapping = self.CONFIG.get("regex_mapping")

    @pytest.mark.parametrize(
        "config_change, error, msg",
        [
            ({"outputs": [{"kafka": "topic"}]}, None, None),
            ({"outputs": []}, ValueError, "Length of 'outputs' must be => 1"),
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
                Factory.create({"name": config}, self.logger)
        else:
            Factory.create({"name": config}, self.logger)

    @pytest.mark.parametrize("testcase, rule, event, expected, regex_mapping", test_cases)
    def test_testcases(self, testcase, rule, event, expected, regex_mapping):
        if regex_mapping is not None:
            self.regex_mapping = regex_mapping
        self._load_specific_rule(rule)
        self.object.process(event)
        assert event == expected, testcase
        if rule.get("pseudonymizer").get("url_fields") is None:
            assert len(self.object.pseudonyms) > 0 and set(self.object.pseudonyms[0]) == {
                "pseudonym",
                "origin",
            }

    # @pytest.mark.parametrize("testcase, rule, event, expected, regex_mapping", failure_test_cases)
    # def test_testcases_failure_handling(
    #     self, caplog, testcase, rule, event, expected, regex_mapping
    # ):
    #     if regex_mapping is not None:
    #         self.regex_mapping = regex_mapping
    #     self._load_specific_rule(rule)
    #     with caplog.at_level(logging.WARNING):
    #         self.object.process(event)
    #     assert re.match(".*ProcessingWarning.*", caplog.text)
    #     assert event == expected, testcase

    def test_tld_extractor_uses_file(self):
        config = deepcopy(self.CONFIG)
        config["tld_lists"] = [TLD_LIST]
        object_with_tld_list = Factory.create({"pseudonymizer": config}, self.logger)
        assert len(object_with_tld_list._tld_extractor.suffix_list_urls) == 1
        assert object_with_tld_list._tld_extractor.suffix_list_urls[0].endswith(
            "tests/testdata/mock_external/tld_list.dat",
        )

    def test_recently_stored_pseudonyms_are_not_stored_again(self):
        self.object._cache._max_timedelta = CACHE_MAX_TIMEDELTA
        event = {"event_id": 1234, "something": "something"}

        rule_dict = {
            "filter": "event_id: 1234",
            "pseudonymizer": {"pseudonyms": {"something": "RE_WHOLE_FIELD"}},
            "description": "description content irrelevant for these tests",
        }

        self._load_specific_rule(rule_dict)
        for index in range(3):
            copied_event = deepcopy(event)
            self.object.process(copied_event)
            pseudonyms = self.object.pseudonyms
            assert (
                copied_event["something"]
                == "<pseudonym:8d7e9ea64b00d7df5dd7d4e1c9dde8a0b70815eea27bddb67738502f4ea0d2ee>"
            )
            assert len(pseudonyms) == 1, f"step {index}"

            copied_event = deepcopy(event)
            self.object.process(copied_event)
            pseudonyms = self.object.pseudonyms
            assert (
                copied_event["something"]
                == "<pseudonym:8d7e9ea64b00d7df5dd7d4e1c9dde8a0b70815eea27bddb67738502f4ea0d2ee>"
            )
            assert len(pseudonyms) == 0

            time.sleep(CACHE_MAX_TIMEDELTA.total_seconds())

    def _load_specific_rule(self, rule):
        self.object._config.regex_mapping = self.regex_mapping
        del self.object.__dict__["_regex_mapping"]
        super()._load_specific_rule(rule)
        self.object._replace_regex_keywords_by_regex_expression()

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
            "pseudonymizer": {"pseudonyms": {"pseudo_this": regex_pattern}},
            "url_fields": ["do_not_pseudo_this"],
        }
        self.regex_mapping = CAP_GROUP_REGEX_MAPPING
        self._load_specific_rule(rule)
        self.object.process(event)

        assert event["do_not_pseudo_this"] == url
        assert event["pseudo_this"] == pseudonym

    def test_replace_regex_keywords_by_regex_expression_can_be_called_multiple_times(self):
        rule_dict = {
            "filter": "event_id: 1234",
            "pseudonymizer": {"pseudonyms": {"something": "RE_WHOLE_FIELD"}},
            "description": "description content irrelevant for these tests",
        }
        self._load_specific_rule(rule_dict)  # First call
        expected_pattern = re.compile("(.*)")
        assert self.object._specific_tree.rules[0].pseudonyms == {"something": expected_pattern}
        self.object._replace_regex_keywords_by_regex_expression()  # Second Call
        assert self.object._specific_tree.rules[0].pseudonyms == {"something": expected_pattern}

    def test_pseudonymize_string(self):
        assert self.object._pseudonymize_string("foo", []).startswith("<pseudonym:")

    def test_parse_url_parts(self):
        expected = {
            "scheme": "https",
            "auth": None,
            "domain": "test",
            "subdomain": "www",
            "suffix": "de",
            "path": "",
            "query": None,
            "fragment": None,
        }
        assert self.object._parse_url_parts("https://www.test.de") == expected
