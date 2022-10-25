# pylint: disable=missing-docstring
# pylint: disable=protected-access
import datetime
import time
from copy import deepcopy
from pathlib import Path

import pytest
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.factory import Factory
from logprep.processor.pseudonymizer.rule import PseudonymizeRule
from tests.unit.processor.base import BaseProcessorTestCase

CAP_GROUP_REGEX_MAPPING = "tests/testdata/unit/pseudonymizer/pseudonymizer_regex_mapping.yml"

CACHE_MAX_TIMEDELTA = datetime.timedelta(milliseconds=100)

REL_TLD_LIST_PATH = "tests/testdata/mock_external/tld_list.dat"

TLD_LIST = f"file://{Path().absolute().joinpath(REL_TLD_LIST_PATH).as_posix()}"


class TestPseudonymizer(BaseProcessorTestCase):

    CONFIG = {
        "type": "pseudonymizer",
        "pseudonyms_topic": "pseudonyms",
        "pubkey_analyst": "tests/testdata/unit/pseudonymizer/example_analyst_pub.pem",
        "pubkey_depseudo": "tests/testdata/unit/pseudonymizer/example_depseudo_pub.pem",
        "hash_salt": "a_secret_tasty_ingredient",
        "specific_rules": ["tests/testdata/unit/pseudonymizer/rules/specific/"],
        "generic_rules": ["tests/testdata/unit/pseudonymizer/rules/generic/"],
        "regex_mapping": "tests/testdata/unit/pseudonymizer/rules/regex_mapping.yml",
        "max_cached_pseudonyms": 1000000,
        "max_caching_days": 1,
    }

    def setup_method(self) -> None:
        super().setup_method()
        self.regex_mapping = self.CONFIG.get("regex_mapping")

    def test_pseudonymize_event(self):
        event_raw = {"foo": "bar"}
        self.object.process(event_raw)
        pseudonyms = self.object.pseudonyms
        assert event_raw == {"foo": "bar"}
        assert pseudonyms == []

    def test_shut_down(self):
        self.object.shut_down()

    def test_rule_has_no_pseudonymize_field_and_rule_creation_fails(self):
        rule_dict = {
            "filter": "event_id: 1234",
            "something": "RE_WHOLE_FIELD",
            "description": "description content irrelevant for these tests",
        }

        with pytest.raises(
            InvalidRuleDefinitionError,
            match=r"config not under key pseudonymize",
        ):
            PseudonymizeRule._create_from_dict(rule_dict)

    def test_rule_has_pseudonymize_field_and_rule_creation_succeeds(self):
        rule_dict = {
            "filter": "event_id: 1234",
            "pseudonymize": {"something": "RE_WHOLE_FIELD"},
            "description": "description content irrelevant for these tests",
        }

        PseudonymizeRule._create_from_dict(rule_dict)

    def test_pseudonymization_of_field_succeeds(self):
        event = {"event_id": 1234, "something": "something"}

        rule_dict = {
            "filter": "event_id: 1234",
            "pseudonymize": {"something": "RE_WHOLE_FIELD"},
            "description": "description content irrelevant for these tests",
        }

        self._load_specific_rule(rule_dict)

        self.object.process(event)
        pseudonyms = self.object.pseudonyms

        assert (
            event["something"]
            == "<pseudonym:8d7e9ea64b00d7df5dd7d4e1c9dde8a0b70815eea27bddb67738502f4ea0d2ee>"
        )
        assert len(pseudonyms) == 1 and set(pseudonyms[0]) == {"pseudonym", "origin"}

    def test_init_tld_extractor_uses_file(self):
        config = deepcopy(self.CONFIG)
        config["tld_lists"] = [TLD_LIST]
        object_with_tld_list = Factory.create({"pseudonymizer": config}, self.logger)
        object_with_tld_list._init_tld_extractor()
        assert len(object_with_tld_list._tld_extractor.suffix_list_urls) == 1
        assert object_with_tld_list._tld_extractor.suffix_list_urls[0].endswith(
            "tests/testdata/mock_external/tld_list.dat",
        )

    def test_recently_stored_pseudonyms_are_not_stored_again(self):
        self.object._cache_max_timedelta = CACHE_MAX_TIMEDELTA
        self.object.setup()
        event = {"event_id": 1234, "something": "something"}

        rule_dict = {
            "filter": "event_id: 1234",
            "pseudonymize": {"something": "RE_WHOLE_FIELD"},
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
        self.object._load_regex_mapping(self.regex_mapping)
        super()._load_specific_rule(rule)
        self.object._replace_regex_keywords_by_regex_expression()

    def test_pseudonymization_of_field_fails_because_filter_does_not_match(self):
        event = {"event_id": 1105, "something": "Not pseudonymized"}

        rule_dict = {
            "filter": "event_id: 1234",
            "pseudonymize": {"something": "RE_WHOLE_FIELD"},
            "description": "description content irrelevant for these tests",
        }

        self._load_specific_rule(rule_dict)

        self.object.process(event)

        assert event["something"] == "Not pseudonymized"

    def test_pseudonymization_of_field_does_not_happen_if_already_pseudonymized(self):
        event = {"event_id": 1234, "something": "Not pseudonymized"}

        rule_dict = {
            "filter": "event_id: 1234",
            "pseudonymize": {"something": "RE_WHOLE_FIELD"},
            "description": "description content irrelevant for these tests",
        }

        self._load_specific_rule(deepcopy(rule_dict))

        self.object.process(event)

        assert (
            event["something"]
            == "<pseudonym:df61c2571842de3f30f4ca2d17a074fccda62945fceeb5636426a0a59347e596>"
        )

    def test_pseudonymize_only_matching_event_field(self):
        event = {"event_id": 1234, "something": "Not pseudonymized"}

        event_other_id = {"event_id": 5678, "something": "Not pseudonymized"}

        rule_dict = {
            "filter": "event_id: 1234",
            "pseudonymize": {"something": "RE_WHOLE_FIELD"},
            "description": "description content irrelevant for these tests",
        }

        self._load_specific_rule(rule_dict)

        self.object.process(event)
        self.object.process(event_other_id)

        assert (
            event["something"]
            == "<pseudonym:df61c2571842de3f30f4ca2d17a074fccda62945fceeb5636426a0a59347e596>"
        )
        assert event_other_id["something"] == "Not pseudonymized"

    def test_pseudonymize_two_fields(self):
        event = {
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "param1": "Pseudonymize me.",
                    "param2": "Pseudonymize me!",
                },
            }
        }

        expected = deepcopy(event)
        expected["winlog"]["event_data"][
            "param1"
        ] = "<pseudonym:8f86699f51fc217651b1512f0bc0a2fa7717ffc700fe3e5426229a6ab063b47a>"
        expected["winlog"]["event_data"][
            "param2"
        ] = "<pseudonym:c40348196f85b761e0633fa568a79c751201a50d63f3a92195985e92cdee2077>"

        rule_dict = {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymize": {
                "winlog.event_data.param1": "RE_WHOLE_FIELD",
                "winlog.event_data.param2": "RE_WHOLE_FIELD",
            },
            "description": "description content irrelevant for these tests",
        }

        self._load_specific_rule(rule_dict)

        self.object.process(event)

        assert event == expected

    def test_pseudonymization_from_specific_rule_files(self):
        event = {
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "param1": "Pseudonymize me.",
                    "param2": "Pseudonymize me!",
                },
            }
        }

        self.object.process(event)

        assert (
            event["winlog"]["event_data"]["param1"]
            == "<pseudonym:8f86699f51fc217651b1512f0bc0a2fa7717ffc700fe3e5426229a6ab063b47a>"
        )
        assert (
            event["winlog"]["event_data"]["param2"]
            == "<pseudonym:c40348196f85b761e0633fa568a79c751201a50d63f3a92195985e92cdee2077>"
        )

    def test_pseudonymization_from_generic_rule_files(self):
        event = {
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "IpAddress": "Pseudonymize me.",
                    "Something": "Do not pseudonymize me.",
                },
            }
        }

        for generic_rule in self.generic_rules:
            self._load_specific_rule(generic_rule)

        self.object.process(event)

        assert (
            event["winlog"]["event_data"]["IpAddress"]
            == "<pseudonym:8f86699f51fc217651b1512f0bc0a2fa7717ffc700fe3e5426229a6ab063b47a>"
        )
        assert event["winlog"]["event_data"]["Something"] == "Do not pseudonymize me."

    def test_pseudonymize_with_specific_and_generic_rule_files(self):
        event = {
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "IpAddress": "Do not pseudonymize me.",
                    "param2": "Pseudonymize me!",
                },
            }
        }

        self.object.process(event)

        assert (
            event["winlog"]["event_data"]["param2"]
            == "<pseudonym:c40348196f85b761e0633fa568a79c751201a50d63f3a92195985e92cdee2077>"
        )
        assert (
            event["winlog"]["event_data"]["IpAddress"]
            == "<pseudonym:b1bbf05c20b28a0eecadff024b3e8a4496bd4d884236ef0b9f59523abe99f488>"
        )

    def test_pseudonymize_with_specific_and_generic_rule_files_with_setup(self):
        event = {
            "winlog": {
                "event_id": 1234,
                "provider_name": "Test456",
                "event_data": {
                    "IpAddress": "Do not pseudonymize me.",
                    "param2": "Pseudonymize me!",
                },
            }
        }

        self.object.setup()
        self.object.process(event)

        assert (
            event["winlog"]["event_data"]["param2"]
            == "<pseudonym:c40348196f85b761e0633fa568a79c751201a50d63f3a92195985e92cdee2077>"
        )
        assert (
            event["winlog"]["event_data"]["IpAddress"]
            == "<pseudonym:b1bbf05c20b28a0eecadff024b3e8a4496bd4d884236ef0b9f59523abe99f488>"
        )

    def test_match_regex_mapping_with_partial_match(self):
        event = {
            "winlog": {
                "event_id": 789,
                "provider_name": "Test123",
                "event_data": {"param1": r"DOMAIN\pseudonymize me!"},
            }
        }

        self.object.process(event)
        expected = (
            r"DOMAIN\<pseudonym:fd5ada8080bcb4a2bcf094bb7aaa7cb907fabeebfff8650676676632cdf4ac4c>"
        )
        assert event["winlog"]["event_data"]["param1"] == expected

    def test_do_not_match_regex_mapping(self):
        event = {
            "event_id": 789,
            "provider_name": "Test123",
            "winlog": {"event_data": {"param1": r"!\pseudonymize me!"}},
        }

        self.object.process(event)

        assert event["winlog"]["event_data"]["param1"] == r"!\pseudonymize me!"

    def test_match_replace_whole_field(self):
        expected = r"<pseudonym:08572d32bb4e3aa23a7673fbb633814d62b603bb75b27d8fc9ea4f7b5476478e>"

        event_whole_field_with_cap = self._pseudo_source_by_pattern(
            r"to be pseudonymized", "RE_WHOLE_FIELD_CAP"
        )
        assert event_whole_field_with_cap["pseudo_this"] == expected

        event_whole_field_empty_cap = self._pseudo_source_by_pattern(
            r"to be pseudonymized", "RE_WHOLE_FIELD_EMPTY_CAPS"
        )
        assert event_whole_field_empty_cap["pseudo_this"] == expected

    def test_match_capture_group_surrounded(self):
        pseudonym = "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
        expected = "KEEP_THIS+" + pseudonym + "+KEEP_THIS"

        event = self._pseudo_source_by_pattern(r"KEEP_THIS+PSEUDO_THIS+KEEP_THIS", "RE_CAP")
        assert event["pseudo_this"] == expected

    def test_match_capture_group_right(self):
        pseudonym = "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
        expected = "KEEP_THIS+" + pseudonym

        event = self._pseudo_source_by_pattern(r"KEEP_THIS+PSEUDO_THIS", "RE_PATTERN_CAP")
        assert event["pseudo_this"] == expected

    def test_match_capture_group_left(self):
        pseudonym = "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
        expected = pseudonym + "+KEEP_THIS"

        event = self._pseudo_source_by_pattern(r"PSEUDO_THIS+KEEP_THIS", "RE_CAP_PATTERN")
        assert event["pseudo_this"] == expected

    def test_match_two_capture_groups_covering_match(self):
        pseudonym_1 = "<pseudonym:c293a7d15377738f5966d78da53f3ba500f3d287a1fdea98bdb225da6212ff68>"
        pseudonym_2 = "<pseudonym:2c868c09bcc9ee59486e915ad2865d33f22b045ea0050215d7f99fd55b12a5d3>"
        expected = pseudonym_1 + pseudonym_2

        event = self._pseudo_source_by_pattern(r"_PSEUDO_THIS_1__PSEUDO_THIS_2_", "RE_TWO_CAPS")
        assert event["pseudo_this"] == expected

    def test_match_two_capture_groups_with_gap(self):
        pseudonym = "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
        expected = pseudonym + "+KEEP_THIS+" + pseudonym

        event = self._pseudo_source_by_pattern(
            r"PSEUDO_THIS+KEEP_THIS+PSEUDO_THIS", "RE_TWO_CAPS_WITH_GAP"
        )
        assert event["pseudo_this"] == expected

    def test_do_not_pseudonymize_url(self):
        expected = "https://test.de"

        event = self._pseudo_with_url("https://test.de", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_do_not_pseudonymize_url_without_scheme(self):
        expected = "test.de"

        event = self._pseudo_with_url("test.de", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_url_subdomain(self):
        subdomain_pseudonym = (
            "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
        )
        expected = f"https://{subdomain_pseudonym}.test.de"

        event = self._pseudo_with_url("https://www.test.de", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_url_subdomain_without_scheme(self):
        subdomain_pseudonym = (
            "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
        )
        expected = f"{subdomain_pseudonym}.test.de"

        event = self._pseudo_with_url("www.test.de", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_url_path(self):
        path_pseudonym = (
            "<pseudonym:f285389e9dc7921109e18f2f1375b26cb47bbe2981d8399ee7e70c3fd156337f>"
        )
        expected = f"https://test.de/{path_pseudonym}"

        event = self._pseudo_with_url("https://test.de/some/path", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_url_query(self):
        query_pseudonym_b = (
            "<pseudonym:4c77fcd97a3d4d98eb062561c37e4ef000f0476bdf153b25ba8031f90ac89877>"
        )
        query_pseudonym_d = (
            "<pseudonym:2344d07c391a619a9b16d1e8cfd5252e5aacf93faaf822712948b9a2fd84fce3>"
        )
        expected = f"https://test.de/?a={query_pseudonym_b}&c={query_pseudonym_d}"

        event = self._pseudo_with_url("https://test.de/?a=b&c=d", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_url_query_substrings(self):
        query_pseudonym_b = (
            "<pseudonym:4c77fcd97a3d4d98eb062561c37e4ef000f0476bdf153b25ba8031f90ac89877>"
        )
        query_pseudonym_d = (
            "<pseudonym:2344d07c391a619a9b16d1e8cfd5252e5aacf93faaf822712948b9a2fd84fce3>"
        )
        query_pseudonym_bd = (
            "<pseudonym:49713f9217c2cac56d0e87a6930669f45be876812eff4bd01ec86d6f22578f99>"
        )
        expected = (
            f"https://test.de/?a={query_pseudonym_b}&c={query_pseudonym_d}&e={query_pseudonym_bd}"
        )
        event = self._pseudo_with_url("https://test.de/?a=b&c=d&e=bd", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_url_subdomain_in_sentence(self):
        subdomain_pseudonym = (
            "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
        )
        expected = f"This is https://{subdomain_pseudonym}.test.de !"

        event = self._pseudo_with_url("This is https://www.test.de !", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_two_identical_urls_subdomain(self):
        subdomain_pseudonym = (
            "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
        )
        expected = f"https://{subdomain_pseudonym}.test.de https://{subdomain_pseudonym}.test.de"

        event = self._pseudo_with_url("https://www.test.de https://www.test.de", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_two_different_urls(self):
        path_pseudonym = (
            "<pseudonym:f285389e9dc7921109e18f2f1375b26cb47bbe2981d8399ee7e70c3fd156337f>"
        )
        subdomain_pseudonym = (
            "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
        )
        expected = (
            f"https://{subdomain_pseudonym}.other.de/{path_pseudonym} "
            f"https://{subdomain_pseudonym}.test.de"
        )
        event = self._pseudo_with_url(
            "https://www.other.de/some/path https://www.test.de",
            "RE_ALL_NO_CAP",
        )
        assert event["pseudo_this"] == expected

    def test_pseudonymize_url_username_password(self):
        auth_pseudonym = (
            "<pseudonym:a204fdad51be9a1e4ee63cea128cc8016226e4459fea2d1ed430c180e6f06359>"
        )
        subdomain_pseudonym = (
            "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
        )
        expected = f"https://{auth_pseudonym}@{subdomain_pseudonym}.test.de"

        event = self._pseudo_with_url("https://user:password@www.test.de", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_url_fragment(self):
        fragment = "<pseudonym:d95ac3629be3245d3f5e836c059516ad04081d513d2888f546b783d178b02e5a>"
        expected = f"https://test.de/#{fragment}"

        event = self._pseudo_with_url("https://test.de/#test", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_url_fragment_with_path_and_query(self):
        path_pseudonym = (
            "<pseudonym:25d02f39a74a2bee3e08c5c82577528f70b653f0805ad1c56570829bfb368881>"
        )
        query_pseudonym = (
            "<pseudonym:4c77fcd97a3d4d98eb062561c37e4ef000f0476bdf153b25ba8031f90ac89877>"
        )
        fragment_pseudonym = (
            "<pseudonym:d95ac3629be3245d3f5e836c059516ad04081d513d2888f546b783d178b02e5a>"
        )
        expected = f"https://test.de/{path_pseudonym}?a={query_pseudonym}#{fragment_pseudonym}"
        event = self._pseudo_with_url("https://test.de/test/?a=b#test", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_url_except_port(self):
        fragment = "<pseudonym:d95ac3629be3245d3f5e836c059516ad04081d513d2888f546b783d178b02e5a>"
        expected = f"https://test.de:123/#{fragment}"

        event = self._pseudo_with_url("https://test.de:123/#test", "RE_ALL_NO_CAP")
        assert event["pseudo_this"] == expected

    def test_pseudonymize_no_valid_html(self):
        pseudonym = "<pseudonym:63559e069172188bb713ed6cc634683514c75d6294e90907be1ffcfdddd97865>"
        expected = f"fail://fail.failfailfail https://{pseudonym}.correct.de"

        event = self._pseudo_with_url(
            "fail://fail.failfailfail https://www.correct.de",
            "RE_ALL_NO_CAP",
        )
        assert event["pseudo_this"] == expected

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
            "pseudonymize": {"pseudo_this": regex_pattern},
            "url_fields": ["do_not_pseudo_this"],
        }
        self.regex_mapping = CAP_GROUP_REGEX_MAPPING
        self._load_specific_rule(rule)
        self.object.process(event)

        assert event["do_not_pseudo_this"] == url
        assert event["pseudo_this"] == pseudonym

    def test_pseudonymize_multiple_url_fields(self):
        pseudonym = "<pseudonym:f742a956bf2ab54f5e7f9cca7caaa33a1b488f6e907cef147fbfb1a99c8de5b6>"
        pseudonymized_url = f"https://{pseudonym}.this.de"

        url = "https://www.pseudo.this.de"
        regex_pattern = "RE_ALL_NO_CAP"
        event = {
            "filter_this": "does_not_matter",
            "pseudo_this": url,
            "and_pseudo_this": url,
        }
        rule = {
            "filter": "filter_this: does_not_matter",
            "pseudonymize": {
                "pseudo_this": regex_pattern,
                "and_pseudo_this": regex_pattern,
            },
            "url_fields": ["pseudo_this", "and_pseudo_this"],
        }
        self._load_specific_rule(rule)
        self.object.process(event)

        assert event["and_pseudo_this"] == pseudonymized_url
        assert event["pseudo_this"] == pseudonymized_url

    def test_pseudonymize_url_and_cap_groups(self):
        pseudonym_cap = (
            "<pseudonym:e92c1d896e9cac51492a29bc4e6415b20e83d37c4a45e4d65e6c3498cdcc5b4b>"
        )
        pseudonym_url = (
            "<pseudonym:f742a956bf2ab54f5e7f9cca7caaa33a1b488f6e907cef147fbfb1a99c8de5b6>"
        )
        pseudonymized = (
            f"SOMETHING {pseudonym_cap} SOMETHING https://{pseudonym_url}.this.de SOMETHING"
        )

        url = "SOMETHING PSEUDO_THIS SOMETHING https://www.pseudo.this.de SOMETHING"
        regex_pattern = "RE_CAP"
        event = {"filter_this": "does_not_matter", "pseudo_this": url}
        rule = {
            "filter": "filter_this: does_not_matter",
            "pseudonymize": {"pseudo_this": regex_pattern},
            "url_fields": ["pseudo_this"],
        }
        self.regex_mapping = CAP_GROUP_REGEX_MAPPING
        self._load_specific_rule(rule)
        self.object.process(event)

        assert event["pseudo_this"] == pseudonymized

    def _pseudo_source_by_pattern(self, source_field, regex_pattern):
        event = {"filter_this": "does_not_matter", "pseudo_this": source_field}
        rule = {
            "filter": "filter_this: does_not_matter",
            "pseudonymize": {"pseudo_this": regex_pattern},
        }
        self.regex_mapping = CAP_GROUP_REGEX_MAPPING
        self._load_specific_rule(rule)
        self.object.process(event)
        return event

    def _pseudo_with_url(self, source_field, regex_pattern):
        event = {"filter_this": "does_not_matter", "pseudo_this": source_field}
        rule = {
            "filter": "filter_this: does_not_matter",
            "pseudonymize": {"pseudo_this": regex_pattern},
            "url_fields": ["pseudo_this"],
        }
        self.regex_mapping = CAP_GROUP_REGEX_MAPPING
        self._load_specific_rule(rule)
        self.object.process(event)
        return event
