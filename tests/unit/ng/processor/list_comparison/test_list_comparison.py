# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
import time
from pathlib import Path
from string import Template
from unittest import mock

import pytest
import responses

from logprep.factory import Factory
from logprep.ng.event.log_event import LogEvent
from logprep.ng.processor.list_comparison.processor import ListComparison
from logprep.processor.base.exceptions import FieldExistsWarning, ProcessingWarning
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import HttpGetter, RefreshableGetterError, refresh_getters
from tests.unit.ng.processor.base import BaseProcessorTestCase


class TestListComparison(BaseProcessorTestCase[ListComparison]):
    CONFIG = {
        "type": "ng_list_comparison",
        "rules": ["tests/testdata/unit/list_comparison/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        "list_search_base_path": "tests/testdata/unit/list_comparison/rules",
    }

    async def setup_method(self):
        await super().setup_method()
        await self.object.setup()

    async def test_element_in_list(self):
        document = {"user": "Franz"}
        expected = {"user": "Franz", "user_results": {"in_list": ["user_list.txt"]}}
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)
        assert log_event.data == expected

    async def test_list_comparison_uses_rule_level_list_search_base_path_without_processor_base_path(
        self,
    ):
        document = {"user": "Franz"}
        log_event = LogEvent(document, original=b"")
        expected = {"user": "Franz", "user_results": {"in_list": ["user_list.txt"]}}
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_search_base_path": self.CONFIG["list_search_base_path"],
                "list_file_paths": ["../lists/user_list.txt"],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
        }
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()
        await processor.process(log_event)

        assert log_event.data == expected

    async def test_element_not_in_list(self):
        # Test if user Charlotte is not in user list
        document = {"user": "Charlotte"}
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)
        assert len(log_event.data.get("user_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("user_results", {}).get("in_list") is None

    async def test_element_in_two_lists(self):
        # Tests if the system name Franz appears in two lists, username Mark is in no list
        document = {"user": "Mark", "system": "Franz"}
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)

        assert len(log_event.data.get("user_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("user_results", {}).get("in_list") is None
        assert len(log_event.data.get("user_and_system_results", {}).get("in_list")) == 2
        assert log_event.data.get("user_and_system_results", {}).get("not_in_list") is None

    async def test_element_not_in_two_lists(self):
        # Tests if the system Gamma does not appear in two lists,
        # and username Mark is also not in list
        document = {"user": "Mark", "system": "Gamma"}
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)

        assert len(log_event.data.get("user_and_system_results", {}).get("not_in_list")) == 2
        assert log_event.data.get("user_and_system_results", {}).get("in_list") is None
        assert len(log_event.data.get("user_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("user_results", {}).get("in_list") is None

    async def test_two_lists_with_one_matched(self):
        document = {"system": "Alpha", "user": "Charlotte"}
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)

        assert len(log_event.data.get("user_results", {}).get("not_in_list")) != 0
        assert log_event.data.get("user_results", {}).get("in_list") is None
        assert log_event.data.get("user_and_system_results", {}).get("not_in_list") is None
        assert len(log_event.data.get("user_and_system_results", {}).get("in_list")) != 0

    async def test_dotted_output_field(self):
        # tests if outputting list_comparison results to dotted fields works
        document = {"dot_channel": "test", "user": "Franz"}
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)

        assert log_event.data.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        log_event.data = {"dot_channel": "test", "user": "Franz"}

        await self.object.process(log_event)

        assert (
            log_event.data.get("more", {})
            .get("than", {})
            .get("dotted", {})
            .get("user_results", {})
            .get("not_in_list")
            is None
        )

    async def test_extend_dotted_output_field(self):
        # tests if list_comparison properly extends lists already present in output fields.
        document = {
            "user": "Franz",
            "dotted": {"user_results": {"in_list": ["already_present"]}},
        }
        log_event = LogEvent(document, original=b"")

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        await self.object.process(log_event)

        assert log_event.data.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        assert len(log_event.data.get("dotted", {}).get("user_results", {}).get("in_list")) == 2

    async def test_dotted_parent_field_exists_but_subfield_doesnt(self):
        # tests if list_comparison properly extends lists already present in output fields.
        document = {
            "user": "Franz",
            "dotted": {"preexistent_output_field": {"in_list": ["already_present"]}},
        }

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)

        assert log_event.data.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        assert len(log_event.data.get("dotted", {}).get("user_results", {}).get("in_list")) == 1
        assert (
            len(log_event.data.get("dotted", {}).get("preexistent_output_field", {}).get("in_list"))
            == 1
        )

    async def test_target_field_exists_and_cant_be_extended(self):
        document = {"dot_channel": "test", "user": "Franz", "dotted": "dotted_Franz"}
        expected = {
            "dot_channel": "test",
            "user": "Franz",
            "dotted": "dotted_Franz",
            "tags": ["_list_comparison_failure"],
        }

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()

        log_event = LogEvent(document, original=b"")
        result = await self.object.process(log_event)

        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert log_event.data == expected

    async def test_intermediate_output_field_is_wrong_type(self):
        document = {
            "dot_channel": "test",
            "user": "Franz",
            "dotted": {"user_results": ["do_not_look_here"]},
        }
        expected = {
            "tags": ["_list_comparison_failure"],
            "dot_channel": "test",
            "user": "Franz",
            "dotted": {"user_results": ["do_not_look_here"]},
        }

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results.do_not_look_here",
                "list_file_paths": ["../lists/user_list.txt"],
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        log_event = LogEvent(document, original=b"")
        result = await self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert log_event.data == expected

    async def test_check_in_dotted_subfield(self):
        document = {"channel": {"type": "fast"}}
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)

        assert len(log_event.data.get("channel_results", {}).get("not_in_list")) == 2
        assert log_event.data.get("channel_results", {}).get("in_list") is None

    async def test_ignore_comment_in_list(self):
        # Tests for a comment inside a list, but as a field inside a document to check
        # if the comment is actually ignored
        document = {"user": "# This is a doc string for testing"}
        log_event = LogEvent(document, original=b"")
        await self.object.process(log_event)

        assert len(log_event.data.get("user_results", {}).get("not_in_list")) == 1
        assert log_event.data.get("user_results", {}).get("in_list") is None

    async def test_delete_source_field(self):
        document = {"user": "Franz"}
        log_event = LogEvent(document, original=b"")

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["../lists/user_list.txt"],
                "delete_source_fields": True,
            },
            "description": "",
        }
        expected = {"user_results": {"in_list": ["user_list.txt"]}}
        await self._load_rule(rule_dict)
        await self.object.setup()
        await self.object.process(log_event)
        assert log_event.data == expected

    async def test_overwrite_target_field(self):
        document = {"user": "Franz"}
        log_event = LogEvent(document, original=b"")

        expected = {"user": "Franz", "tags": ["_list_comparison_failure"]}
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user",
                "list_file_paths": ["../lists/user_list.txt"],
                "overwrite_target": True,
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        result = await self.object.process(log_event)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    @responses.activate
    async def test_list_comparison_loads_rule_with_http_template_in_list_search_base_path(self):
        url = "http://localhost/tests/testdata/bad_users.list?ref=bla"
        responses.add(
            responses.GET,
            url,
            """Franz
Heinz
Hans
""",
        )
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["bad_users.list"],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla",
        }
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()
        assert processor.rules[0].compare_sets == {url: {"Franz", "Heinz", "Hans"}}

    @responses.activate
    async def test_list_comparison_loads_rule_using_http_and_updates_with_callback(self, tmp_path):
        target = "localhost/tests/testdata/bad_users.list?ref=bla"
        url = f"http://{target}"
        responses.add(
            responses.GET,
            url,
            """Franz
Heinz
Hans
""",
        )
        responses.add(
            responses.GET,
            url,
            """Franz
Heinz
""",
        )
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["bad_users.list"],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla",
        }

        HttpGetter._shared.clear()

        getter_file_content = {url: {"refresh_interval": 10}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            processor = Factory.create({"custom_lister": config})
            rule = processor.rule_class.create_from_dict(rule_dict)
            processor._rule_tree.add_rule(rule)

            await processor.setup()
            assert processor.rules[0].compare_sets == {url: {"Franz", "Heinz", "Hans"}}
            assert processor.rules[0].compare_sets == {url: {"Franz", "Heinz", "Hans"}}
            HttpGetter(target=url, protocol="http").scheduler.run_all()
            assert processor.rules[0].compare_sets == {url: {"Franz", "Heinz"}}

    @responses.activate
    async def test_list_comparison_resolves_dynamic_http_template_from_event(self):
        document = {"tenant": "acme", "user": "Foo"}
        log_event = LogEvent(document, original=b"")
        url_template = "http://localhost/${tenant}/${LOGPREP_LIST}"
        list_name = "bad_users.list"
        url = "http://localhost/acme/bad_users.list"
        expected = {
            "tenant": "acme",
            "user": "Foo",
            "user_results": {"in_list": [url]},
        }

        responses.add(responses.GET, url=url, body="Foo\nBar\n", status=200)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_name],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        await processor.setup()
        assert rule.compare_sets == {}
        assert len(responses.calls) == 0

        await processor.process(log_event)

        assert document == expected
        assert rule.compare_sets == {url: {"Foo", "Bar"}}
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

    @responses.activate
    async def test_list_comparison_reuses_dynamic_http_compare_set_and_signals_activity(self):
        first_document = {"tenant": "acme", "user": "Foo"}
        second_document = {"tenant": "acme", "user": "Bar"}
        first_log_event = LogEvent(first_document, original=b"")
        second_log_event = LogEvent(second_document, original=b"")
        url_template = "http://localhost/${tenant}/${LOGPREP_LIST}"
        list_name = "bad_users.list"
        url = "http://localhost/acme/bad_users.list"

        responses.add(responses.GET, url=url, body="Foo\nBar\n", status=200)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_name],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()

        with mock.patch("logprep.util.getter.time.monotonic", side_effect=[100.0, 125.0]):
            await processor.process(first_log_event)
            assert HttpGetter._shared[url].last_called == 100.0

            await processor.process(second_log_event)
            assert HttpGetter._shared[url].last_called == 125.0

        assert len(responses.calls) == 1
        assert first_document["user_results"] == {"in_list": [url]}
        assert second_document["user_results"] == {"in_list": [url]}

    @responses.activate
    async def test_list_comparison_dynamic_not_in_list_uses_current_event_compare_set(self):
        first_document = {"tenant": "acme", "user": "Foo"}
        second_document = {"tenant": "beta", "user": "Missing"}
        first_log_event = LogEvent(first_document, original=b"")
        second_log_event = LogEvent(second_document, original=b"")
        url_template = "http://localhost/${tenant}/${LOGPREP_LIST}"
        list_name = "bad_users.list"
        first_url = "http://localhost/acme/bad_users.list"
        second_url = "http://localhost/beta/bad_users.list"
        expected_second_document = {
            "tenant": "beta",
            "user": "Missing",
            "user_results": {"not_in_list": [second_url]},
        }

        responses.add(responses.GET, url=first_url, body="Foo\n", status=200)
        responses.add(responses.GET, url=second_url, body="Bar\n", status=200)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_name],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()

        await processor.process(first_log_event)
        await processor.process(second_log_event)

        assert first_document["user_results"] == {"in_list": [first_url]}
        assert second_document == expected_second_document
        assert rule.compare_sets == {
            first_url: {"Foo"},
            second_url: {"Bar"},
        }

    @responses.activate
    async def test_list_comparison_dynamic_empty_http_list_is_used_for_not_in_list(self):
        document = {"tenant": "acme", "user": "Foo"}
        log_event = LogEvent(document, original=b"")
        url_template = "http://localhost/${tenant}/${LOGPREP_LIST}"
        list_name = "bad_users.list"
        url = "http://localhost/acme/bad_users.list"
        expected = {
            "tenant": "acme",
            "user": "Foo",
            "user_results": {"not_in_list": [url]},
        }

        responses.add(responses.GET, url=url, body="", status=200)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_name],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()

        await processor.process(log_event)

        assert document == expected
        assert rule.compare_sets == {url: set()}

    @responses.activate
    async def test_list_comparison_dynamic_http_template_rejects_non_scalar_event_values(self):
        document = {"tenant": ["acme"], "user": "Foo"}
        log_event = LogEvent(document, original=b"")
        expected = {
            "tenant": ["acme"],
            "user": "Foo",
            "tags": ["_list_comparison_failure"],
        }
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["bad_users.list"],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/${tenant}/${LOGPREP_LIST}",
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()

        result = await processor.process(log_event)

        assert document == expected
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert "value for list comparison field 'tenant' is not a scalar value" in str(
            result.warnings[0]
        )
        assert len(responses.calls) == 0

    @responses.activate
    async def test_list_comparison_dynamic_http_template_adds_failure_tag_if_event_field_is_missing(
        self,
    ):
        document = {"user": "Foo"}
        log_event = LogEvent(document, original=b"")
        expected = {
            "user": "Foo",
            "tags": ["_list_comparison_failure"],
        }
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["bad_users.list"],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/${tenant}/${LOGPREP_LIST}",
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()

        result = await processor.process(log_event)

        assert document == expected
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert "missing event field 'tenant' for dynamic list comparison path" in str(
            result.warnings[0]
        )
        assert len(responses.calls) == 0

    @responses.activate
    async def test_list_comparison_dynamic_http_failure_does_not_mark_rule_failed(self):
        failed_document = {"tenant": "acme", "user": "Foo"}
        successful_document = {"tenant": "beta", "user": "Foo"}
        failed_log_event = LogEvent(failed_document, original=b"")
        successful_log_event = LogEvent(successful_document, original=b"")
        url_template = "http://localhost/${tenant}/${LOGPREP_LIST}"
        failed_url = "http://localhost/acme/bad_users.list"
        successful_url = "http://localhost/beta/bad_users.list"
        expected_failed_document = {
            "tenant": "acme",
            "user": "Foo",
            "tags": ["_list_comparison_failure"],
        }
        expected_successful_document = {
            "tenant": "beta",
            "user": "Foo",
            "user_results": {"in_list": [successful_url]},
        }

        responses.add(responses.GET, url=failed_url, status=500)
        responses.add(responses.GET, url=successful_url, body="Foo\n", status=200)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["bad_users.list"],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()

        result = await processor.process(failed_log_event)

        assert failed_document == expected_failed_document
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert rule.data_error is None
        assert failed_url not in rule.compare_sets
        assert len(HttpGetter._shared[failed_url].callbacks) == 0
        assert len(HttpGetter._shared[failed_url].cleanup_callbacks) == 0

        await processor.process(successful_log_event)

        assert successful_document == expected_successful_document
        assert rule.data_error is None
        assert rule.compare_sets == {successful_url: {"Foo"}}

    async def test_list_comparison_does_not_add_duplicates_from_list_source(self):
        document = {"users": ["Franz", "Alpha"]}
        log_event = LogEvent(document, original=b"")
        expected = {
            "users": ["Franz", "Alpha"],
            "user_results": {
                "in_list": [
                    "system_list.txt",
                    "user_list.txt",
                ]
            },
        }
        rule_dict = {
            "filter": "users",
            "list_comparison": {
                "source_fields": ["users"],
                "target_field": "user_results",
                "list_file_paths": [
                    "../lists/system_list.txt",
                    "../lists/user_list.txt",
                ],
            },
            "description": "",
        }
        await self._load_rule(rule_dict)
        await self.object.setup()
        await self.object.process(log_event)
        assert document == expected

    @pytest.mark.parametrize(
        "testcase, system, result",
        [
            ("string in list", "Alpha", {"in_list": ["system_list.txt"]}),
            ("string not in list", "Omega", {"not_in_list": ["system_list.txt"]}),
            ("list element in list", ["Alpha"], {"in_list": ["system_list.txt"]}),
            ("list element not in list", ["Omega"], {"not_in_list": ["system_list.txt"]}),
            ("one list element in list", ["Alpha", "Omega"], {"in_list": ["system_list.txt"]}),
            ("multiple list elements in list", ["Alpha", "Beta"], {"in_list": ["system_list.txt"]}),
        ],
    )
    async def test_match_list_field(self, testcase, system, result):
        document = {"system": system}
        log_event = LogEvent(document, original=b"")
        expected = {"system": system, "system_results": result}
        rule_dict = {
            "filter": "system",
            "list_comparison": {
                "source_fields": ["system"],
                "target_field": "system_results",
                "list_file_paths": ["../lists/system_list.txt"],
            },
            "description": "",
        }
        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": self.CONFIG["list_search_base_path"],
        }
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        await processor.setup()
        await processor.process(log_event)
        assert document == expected, testcase

    @pytest.mark.parametrize(
        ("json_content", "content_field"),
        [
            pytest.param({None: ["Franz", "Heinz", "Hans"]}, ""),
            pytest.param({None: ["Franz", "Heinz", "Hans"]}, None),
            pytest.param({"": ["Franz", "Heinz", "Hans"]}, ""),
            pytest.param({"": ["Franz", "Heinz", "Hans"]}, None),
        ],
    )
    def test_list_comparison_fail_on_json_list_load_from_file(
        self, json_content, content_field, tmp_path
    ):
        file_content = json.dumps(json_content)
        file_name = "file.json"
        file_root_path = tmp_path
        file_path = file_root_path / file_name

        with open(file_path, "w") as f:
            f.write(file_content)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [file_name],
                "content_field": content_field,
            },
            "description": "",
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": str(file_root_path),
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        with pytest.raises(ValueError, match="Content is not a list"):
            processor.setup()

    @responses.activate
    def test_list_comparison_process_adds_failure_tag_if_http_list_returns_500(
        self,
        caplog,
    ):
        document = {"user": "Foo"}
        log_event = LogEvent(document, original=b"")
        expected = {
            "tags": ["_list_comparison_failure"],
            "user": "Foo",
        }
        url_template = "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
        list_name = "bad_users.list"
        url = Template(url_template).substitute({"LOGPREP_LIST": list_name})

        responses.add(
            responses.GET,
            url=url,
            status=500,
        )

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_name],
            },
            "description": "",
        }

        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        HttpGetter._shared.clear()

        captured_sessions = []
        original_get_requests_session = HttpGetter._get_requests_session

        def capture_session(self):
            session = original_get_requests_session(self)
            captured_sessions.append(session)
            return session

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        assert rule.data_error is None

        with mock.patch.object(
            HttpGetter,
            "_get_requests_session",
            autospec=True,
            side_effect=capture_session,
        ):
            processor.setup()

        assert isinstance(rule.data_error, RefreshableGetterError)

        assert captured_sessions

        session = captured_sessions[0]
        adapter = session.get_adapter(url)
        retries = adapter.max_retries

        assert retries.total == 3
        assert 500 in retries.status_forcelist

        assert "Caused by ResponseError('too many 500 error responses'))" in caplog.text
        assert "ListComparisonRule failed" in caplog.text

        processor.process(log_event)

        assert document == expected
        assert len(responses.calls) == retries.total + 1
        assert responses.calls[0].request.url == url
        assert rule.compare_sets == {}

    @responses.activate
    def test_list_comparison_recovers_after_failed_http_getter_setup(
        self,
    ):
        document = {"user": "Foo"}
        log_event = LogEvent(document, original=b"")
        expected_failed_document = {
            "user": "Foo",
            "tags": ["_list_comparison_failure"],
        }
        url_template = "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
        list_name = "bad_users.list"
        url = Template(url_template).substitute({"LOGPREP_LIST": list_name})

        responses.add(
            responses.GET,
            url=url,
            status=500,
        )

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_name],
            },
            "description": "",
        }

        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        processor.setup()
        processor.process(log_event)

        assert isinstance(rule.data_error, RefreshableGetterError)
        assert document == expected_failed_document
        assert rule.compare_sets == {}
        assert responses.calls[-1].request.url == url
        assert responses.calls[-1].response.status_code == 500

        # recovered case:
        responses.replace(
            responses.GET,
            url=url,
            body="Foo\n",
            status=200,
        )

        document = {"user": "Foo"}
        log_event = LogEvent(document, original=b"")
        expected_recovered_document = {
            "user": "Foo",
            "user_results": {"in_list": [url]},
        }

        HttpGetter._shared.clear()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        processor.setup()
        processor.process(log_event)

        assert rule.data_error is None
        assert document == expected_recovered_document
        assert rule.compare_sets == {url: {"Foo"}}
        assert responses.calls[-1].request.url == url
        assert responses.calls[-1].response.status_code == 200

    @responses.activate
    def test_list_comparison_recovers_after_failed_http_getter_while_processing(
        self,
        tmp_path,
    ):
        document = {"user": "Foo"}
        log_event = LogEvent(document, original=b"")
        expected_failed_document = {
            "user": "Foo",
            "tags": ["_list_comparison_failure"],
        }
        url_template = "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
        list_name = "bad_users.list"
        url = Template(url_template).substitute({"LOGPREP_LIST": list_name})

        responses.add(
            responses.GET,
            url=url,
            status=500,
        )

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_name],
            },
            "description": "",
        }

        config = {
            "type": "ng_list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        HttpGetter._shared.clear()

        getter_file_content = {url: {"refresh_interval": 1}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        mock_env = {ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}
        with mock.patch.dict("os.environ", mock_env):
            processor = Factory.create({"custom_lister": config})
            rule = processor.rule_class.create_from_dict(rule_dict)
            processor._rule_tree.add_rule(rule)

            processor.setup()
            processor.process(log_event)

            data_error = rule.data_error
            assert isinstance(data_error, RefreshableGetterError)
            assert document == expected_failed_document
            assert rule.compare_sets == {}
            assert responses.calls[-1].request.url == url
            assert responses.calls[-1].response.status_code == 500

            # recovered case:
            responses.replace(
                responses.GET,
                url=url,
                body="Foo\n",
                status=200,
            )

            time.sleep(2)
            refresh_getters()

            assert rule.data_error is None
            assert responses.calls[-1].request.url == url
            assert responses.calls[-1].response.status_code == 200
