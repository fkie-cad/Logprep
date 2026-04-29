# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-many-public-methods
# pylint: disable=too-many-lines
# pylint: disable=too-few-public-methods
# pylint: disable=attribute-defined-outside-init

import re
from copy import deepcopy

import pytest

from logprep.factory import Factory
from logprep.factory_error import InvalidConfigurationError
from logprep.ng.abc.event import OutputSpec
from logprep.ng.event.log_event import LogEvent
from logprep.ng.event.pseudonym_event import PseudonymEvent
from logprep.ng.processor.pseudonymizer.processor import Pseudonymizer
from logprep.util.pseudo.encrypter import (
    DualPKCS1HybridCTREncrypter,
    DualPKCS1HybridGCMEncrypter,
)
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.pseudonymizer.test_pseudonymizer import (
    test_cases as non_ng_test_cases,
)

test_cases = deepcopy(non_ng_test_cases)


class TestPseudonymizer(BaseProcessorTestCase[Pseudonymizer]):
    CONFIG = {
        "type": "ng_pseudonymizer",
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

    async def async_setup(self) -> None:
        await super().async_setup()
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
                "not allowed to have more than one mapping item",
            ),
        ],
    )
    async def test_config_validation(self, config_change, error, msg):
        config = deepcopy(self.CONFIG)
        config |= config_change
        if error:
            with pytest.raises(error, match=msg):
                Factory.create({"name": config})
        else:
            Factory.create({"name": config})

    @pytest.mark.parametrize("testcase, rule, event, expected, regex_mapping", test_cases)
    async def test_testcases(self, testcase, rule, event, expected, regex_mapping):
        if regex_mapping is not None:
            self.regex_mapping = regex_mapping
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        await self.object.process(event)
        assert event.data == expected, testcase

    async def _load_rule(self, rule):
        config = deepcopy(self.CONFIG)
        config["regex_mapping"] = self.regex_mapping
        self.object = Factory.create({"pseudonymizer": config})
        await super()._load_rule(rule)
        await self.object.setup()

    async def test_pseudonymize_url_fields_not_in_pseudonymize(self):
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
        await self._load_rule(rule)
        event = LogEvent(event, original=b"")
        await self.object.process(event)

        assert event.data["do_not_pseudo_this"] == url
        assert event.data["pseudo_this"] == pseudonym

    async def test_replace_regex_keywords_by_regex_expression_is_idempotent(self):
        rule_dict = {
            "filter": "event_id: 1234",
            "pseudonymizer": {"mapping": {"something": "RE_WHOLE_FIELD"}},
            "description": "description content irrelevant for these tests",
        }
        await self._load_rule(rule_dict)  # First call
        expected_pattern = re.compile("(.*)")
        assert self.object._rule_tree.rules[0].pseudonyms == {"something": expected_pattern}
        self.object._replace_regex_keywords_by_regex_expression()  # Second Call
        assert self.object._rule_tree.rules[0].pseudonyms == {"something": expected_pattern}

    async def test_pseudonymize_string_adds_pseudonyms(self):
        self.object._event = LogEvent({"does not": "matter"}, original=b"")
        assert self.object._pseudonymize_string("foo").startswith("<pseudonym:")
        assert len(self.object._event.extra_data) == 1

    async def test_resolve_from_cache_pseudonym(self):
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
        await self._load_rule(rule_dict)
        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0
        event = LogEvent(event, original=b"")
        await self.object.process(event)
        assert self.object.metrics.new_results == 1
        assert self.object.metrics.cached_results == 1
        assert self.object.metrics.num_cache_entries == 1

    async def test_resolve_from_cache_pseudonymize_urls(self):
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
        await self._load_rule(rule_dict)
        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0
        event = LogEvent(event, original=b"")
        await self.object.process(event)
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
    async def test_pseudonymize_url(self, url, expected):
        self.object._event = LogEvent({"does not": "matter"}, original=b"")
        assert self.object._pseudonymize_url(url) == expected

    async def test_process_returns_extra_output(self):
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
        await self._load_rule(rule_dict)  # First call
        event = LogEvent(event, original=b"")
        await self.object.process(event)
        assert len(event.extra_data) == 1, "Should contain only one pseudonym"
        pseudonym_event = event.extra_data[0]
        assert pseudonym_event.data
        assert isinstance(pseudonym_event, PseudonymEvent)
        assert pseudonym_event.outputs == [
            OutputSpec("kafka", "topic"),
        ], "Output is set as in CONFIG"
        assert pseudonym_event.data.get("pseudonym"), "pseudonym is set"
        assert pseudonym_event.data.get("origin"), "encrypted original is set"
        assert pseudonym_event.data.get("@timestamp"), "timestamp is set if present in event"

    async def test_extra_output_contains_only_one_pseudonym_even_if_pseudonym_appears_multiple_times_in_event(
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
        await self._load_rule(rule_dict)
        event = LogEvent(event, original=b"")
        event = await self.object.process(event)
        assert (
            len(event.extra_data) == 1
        ), "Should contain only one pseudonym, as the value for both is the same"
        pseudonym_event = event.extra_data[0]
        assert pseudonym_event
        assert pseudonym_event.outputs == [
            OutputSpec("kafka", "topic"),
        ], "Output is set as in CONFIG"
        assert pseudonym_event.data.get("pseudonym"), "pseudonym is set"
        assert pseudonym_event.data.get("origin"), "encrypted original is set"
        assert pseudonym_event.data.get("@timestamp"), "timestamp is set if present in event"

    async def test_extra_output_contains_different_pseudonyms_for_different_values(self):
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
        await self._load_rule(rule_dict)
        event = LogEvent(event, original=b"")
        event = await self.object.process(event)
        assert len(event.extra_data) == 2, "Should contain two pseudonyms, for each value one"
        pseudonym_1 = event.extra_data[0]
        assert pseudonym_1.data.get("pseudonym"), "pseudonym is set"
        assert pseudonym_1.data.get("origin"), "encrypted original is set"
        assert pseudonym_1.data.get("@timestamp"), "timestamp is set if present in event"

        pseudonym_2 = event.extra_data[1]
        assert pseudonym_2.data.get("pseudonym"), "pseudonym is set"
        assert pseudonym_2.data.get("origin"), "encrypted original is set"
        assert pseudonym_2.data.get("@timestamp"), "timestamp is set if present in event"

        assert pseudonym_1.data.get("pseudonym") != pseudonym_2.data.get(
            "pseudonym"
        ), "pseudonyms should differ"
        assert pseudonym_1.data.get("origin") != pseudonym_2.data.get(
            "origin"
        ), "origins should differ"

    async def test_ignores_missing_field_but_add_warning(self):
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
        await self._load_rule(rule_dict)
        event = LogEvent(event, original=b"")
        extra_output = await self.object.process(event)
        pseudonym_event = extra_output.extra_data[0]
        assert pseudonym_event.data.get("pseudonym"), "pseudonym is set"
        assert "_pseudonymizer_missing_field_warning" in event.data.get("tags", [])
        assert len(event.extra_data) == 1, "only ONE pseudonym is set"

    @pytest.mark.parametrize(
        "mode, encrypter_class",
        [("CTR", DualPKCS1HybridCTREncrypter), ("GCM", DualPKCS1HybridGCMEncrypter)],
    )
    async def test_uses_encrypter(self, mode, encrypter_class):
        config = deepcopy(self.CONFIG)
        config["mode"] = mode
        object_with_encrypter = Factory.create({"pseudonymizer": config})
        assert isinstance(object_with_encrypter._encrypter, encrypter_class)

    async def test_setup_raises_invalid_configuration_on_missing_regex_mapping(self):
        rule_dict = {
            "filter": "winlog.event_id: 1234 AND winlog.provider_name: Test456",
            "pseudonymizer": {
                "mapping": {
                    "winlog.event_data.param2": "RE_WHOLE_FIELD",
                }
            },
        }
        await self._load_rule(rule_dict)
        self.object.rules[0].mapping["winlog.event_data.param2"] = "RE_DOES_NOT_EXIST"
        error_message = (
            r"Regex keyword 'RE_DOES_NOT_EXIST' not found in regex_mapping '.*\/regex_mapping.yml'"
        )
        with pytest.raises(InvalidConfigurationError, match=error_message):
            await self.object.setup()

    async def test_cache_metrics_updated(self):
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
        await self._load_rule(rule_dict)

        self.object.metrics.new_results = 0
        self.object.metrics.cached_results = 0
        self.object.metrics.num_cache_entries = 0
        event = LogEvent(event, original=b"")
        await self.object.process(deepcopy(event))
        await self.object.process(deepcopy(event))
        await self.object.process(event)
        # because the event is the same, the result is cached
        # metrics are mocked by integers and incremented by cache_info results
        assert self.object.metrics.new_results == 3
        assert self.object.metrics.cached_results == 3
        assert self.object.metrics.num_cache_entries == 3
