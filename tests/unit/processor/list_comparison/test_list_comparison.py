# pylint: disable=missing-docstring
# pylint: disable=protected-access
import json
import re
import time
from pathlib import Path
from string import Template
from unittest import mock

import pytest
import responses

from logprep.factory import Factory
from logprep.processor.base.exceptions import FieldExistsWarning, ProcessingWarning
from logprep.processor.list_comparison.rule import ListComparisonRule
from logprep.util.defaults import ENV_NAME_LOGPREP_GETTER_CONFIG
from logprep.util.getter import (
    HttpGetter,
    RefreshableGetter,
    RefreshableGetterError,
    refresh_getters,
)
from tests.conftest import mock_env
from tests.unit.processor.base import BaseProcessorTestCase

NOT_SET = object()
"""A sentinel object to indicate that a value has not been provided."""


def _get_static_set_entries(rule: ListComparisonRule, name: str) -> set[str] | None:
    static_set = next(cs for cs in rule._static_sets if cs.name == name)
    return static_set.content


def _get_first_dynamic_set_entries(
    rule: ListComparisonRule, name: str, uri: str | None = None
) -> set[str] | None:
    dynamic_set = next(cs for cs in rule._dynamic_sets if cs.name == name)
    if uri is None:
        return next(iter(dynamic_set.uri_to_content.values()), None)
    return dynamic_set.uri_to_content[uri]


test_cases = [  # rule, event, expected
    pytest.param(
        {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
        },
        {"user": "Franz"},
        {"user": "Franz", "user_results": {"in_list": ["user_list.txt"]}},
        id="single value is found in the list",
    ),
    pytest.param(
        {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
        },
        {"user": "Charlotte"},
        {"user": "Charlotte", "user_results": {"not_in_list": ["user_list.txt"]}},
        id="single value is not found in the list",
    ),
    pytest.param(
        {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
        },
        {"user": "# This is a doc string for testing"},
        {
            "user": "# This is a doc string for testing",
            "user_results": {"not_in_list": ["user_list.txt"]},
        },
        id="comment lines in the list are ignored",
    ),
    pytest.param(
        {
            "filter": "system",
            "list_comparison": {
                "source_fields": ["system"],
                "target_field": "results",
                "list_file_paths": ["../lists/user_list.txt", "../lists/system_list.txt"],
            },
        },
        {"system": "Alpha"},
        {"system": "Alpha", "results": {"in_list": ["system_list.txt"]}},
        id="value is found in one of two lists",
    ),
    pytest.param(
        {
            "filter": "system",
            "list_comparison": {
                "source_fields": ["system"],
                "target_field": "results",
                "list_file_paths": ["../lists/user_list.txt", "../lists/system_list.txt"],
            },
        },
        {"system": "Gamma"},
        {"system": "Gamma", "results": {"not_in_list": ["user_list.txt", "system_list.txt"]}},
        id="value is found in neither of two lists",
    ),
    pytest.param(
        {
            "filter": "channel",
            "list_comparison": {
                "source_fields": ["channel.type"],
                "target_field": "channel_results",
                "list_file_paths": ["../lists/user_list.txt", "../lists/system_list.txt"],
            },
        },
        {"channel": {"type": "fast"}},
        {
            "channel": {"type": "fast"},
            "channel_results": {"not_in_list": ["user_list.txt", "system_list.txt"]},
        },
        id="dotted source subfield is resolved",
    ),
    pytest.param(
        {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
        },
        {"user": "Franz", "dotted": {"user_results": {"in_list": ["already_present"]}}},
        {
            "user": "Franz",
            "dotted": {"user_results": {"in_list": ["already_present", "user_list.txt"]}},
        },
        id="existing in_list target field is extended",
    ),
    pytest.param(
        {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["../lists/user_list.txt"],
                "delete_source_fields": True,
            },
        },
        {"user": "Franz"},
        {"user_results": {"in_list": ["user_list.txt"]}},
        id="source field is deleted when configured",
    ),
]


failure_test_cases = [  # rule, event, expected, error_message
    pytest.param(
        {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
        },
        {"dot_channel": "test", "user": "Franz", "dotted": "dotted_Franz"},
        {
            "dot_channel": "test",
            "user": "Franz",
            "dotted": "dotted_Franz",
            "tags": ["_list_comparison_failure"],
        },
        r"FieldExistsWarning.*could not be extended: dotted.user_results",
        id="target parent field exists as string and cannot be extended",
    ),
    pytest.param(
        {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results.do_not_look_here",
                "list_file_paths": ["../lists/user_list.txt"],
            },
        },
        {"dot_channel": "test", "user": "Franz", "dotted": {"user_results": ["do_not_look_here"]}},
        {
            "dot_channel": "test",
            "user": "Franz",
            "dotted": {"user_results": ["do_not_look_here"]},
            "tags": ["_list_comparison_failure"],
        },
        r"FieldExistsWarning.*could not be extended: dotted.user_results.do_not_look_here",
        id="intermediate target field has wrong type",
    ),
    pytest.param(
        {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user",
                "list_file_paths": ["../lists/user_list.txt"],
                "overwrite_target": True,
            },
        },
        {"user": "Franz"},
        {"user": "Franz", "tags": ["_list_comparison_failure"]},
        r"FieldExistsWarning.*could not be extended: user",
        id="overwrite target fails when target equals source",
    ),
]


class TestListComparison(BaseProcessorTestCase):
    CONFIG = {
        "type": "list_comparison",
        "rules": ["tests/testdata/unit/list_comparison/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        "list_search_base_path": "tests/testdata/unit/list_comparison/rules",
    }

    def setup_method(self):
        super().setup_method()
        self.object.setup()

    @pytest.mark.parametrize("rule, event, expected", test_cases)
    def test_testcases(self, rule, event, expected):  # pylint: disable=unused-argument
        self._load_rule(rule)
        self.object.setup()
        self.object.process(event)
        assert event == expected

    @pytest.mark.parametrize("rule, event, expected, error_message", failure_test_cases)
    def test_testcases_failure_handling(self, rule, event, expected, error_message):
        self._load_rule(rule)
        self.object.setup()
        result = self.object.process(event)
        assert len(result.warnings) == 1
        assert re.match(rf".*{error_message}", str(result.warnings[0]))
        assert event == expected

    def test_list_comparison_uses_rule_level_list_search_base_path_without_processor_base_path(
        self,
    ):
        document = {"user": "Franz"}
        expected = {"user": "Franz", "user_results": {"in_list": ["user_list.txt"]}}
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_search_base_path": self.CONFIG["list_search_base_path"],
                "list_file_paths": ["../lists/user_list.txt"],
            },
        }
        config = {
            "type": "list_comparison",
            "rules": [],
        }
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        processor.process(document)

        assert document == expected

    def test_element_not_in_list(self):
        # Test if user Charlotte is not in user list
        document = {"user": "Charlotte"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None

    def test_element_in_two_lists(self):
        # Tests if the system name Franz appears in two lists, username Mark is in no list
        document = {"user": "Mark", "system": "Franz"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None
        assert len(document.get("user_and_system_results", {}).get("in_list")) == 2
        assert document.get("user_and_system_results", {}).get("not_in_list") is None

    def test_element_not_in_two_lists(self):
        # Tests if the system Gamma does not appear in two lists,
        # and username Mark is also not in list
        document = {"user": "Mark", "system": "Gamma"}

        self.object.process(document)

        assert len(document.get("user_and_system_results", {}).get("not_in_list")) == 2
        assert document.get("user_and_system_results", {}).get("in_list") is None
        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None

    def test_two_lists_with_one_matched(self):
        document = {"system": "Alpha", "user": "Charlotte"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) != 0
        assert document.get("user_results", {}).get("in_list") is None
        assert document.get("user_and_system_results", {}).get("not_in_list") is None
        assert len(document.get("user_and_system_results", {}).get("in_list")) != 0

    def test_dotted_output_field(self):
        # tests if outputting list_comparison results to dotted fields works
        document = {"dot_channel": "test", "user": "Franz"}

        self.object.process(document)

        assert document.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        document = {"dot_channel": "test", "user": "Franz"}

        self.object.process(document)

        assert (
            document.get("more", {})
            .get("than", {})
            .get("dotted", {})
            .get("user_results", {})
            .get("not_in_list")
            is None
        )

    def test_extend_dotted_output_field(self):
        # tests if list_comparison properly extends lists already present in output fields.
        document = {
            "user": "Franz",
            "dotted": {"user_results": {"in_list": ["already_present"]}},
        }

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "dotted.user_results",
                "list_file_paths": ["../lists/user_list.txt"],
            },
        }
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(document)

        assert document.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        assert len(document.get("dotted", {}).get("user_results", {}).get("in_list")) == 2

    def test_dotted_parent_field_exists_but_subfield_doesnt(self):
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
        }
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(document)

        assert document.get("dotted", {}).get("user_results", {}).get("not_in_list") is None
        assert len(document.get("dotted", {}).get("user_results", {}).get("in_list")) == 1
        assert (
            len(document.get("dotted", {}).get("preexistent_output_field", {}).get("in_list")) == 1
        )

    def test_target_field_exists_and_cant_be_extended(self):
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
        }
        self._load_rule(rule_dict)
        self.object.setup()
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    def test_intermediate_output_field_is_wrong_type(self):
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
        }
        self._load_rule(rule_dict)
        self.object.setup()
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    def test_check_in_dotted_subfield(self):
        document = {"channel": {"type": "fast"}}

        self.object.process(document)

        assert len(document.get("channel_results", {}).get("not_in_list")) == 2
        assert document.get("channel_results", {}).get("in_list") is None

    def test_ignore_comment_in_list(self):
        # Tests for a comment inside a list, but as a field inside a document to check
        # if the comment is actually ignored
        document = {"user": "# This is a doc string for testing"}

        self.object.process(document)

        assert len(document.get("user_results", {}).get("not_in_list")) == 1
        assert document.get("user_results", {}).get("in_list") is None

    def test_delete_source_field(self):
        document = {"user": "Franz"}
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["../lists/user_list.txt"],
                "delete_source_fields": True,
            },
        }
        expected = {"user_results": {"in_list": ["user_list.txt"]}}
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(document)
        assert document == expected

    def test_overwrite_target_field(self):
        document = {"user": "Franz"}
        expected = {"user": "Franz", "tags": ["_list_comparison_failure"]}
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user",
                "list_file_paths": ["../lists/user_list.txt"],
                "overwrite_target": True,
            },
        }
        self._load_rule(rule_dict)
        self.object.setup()
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected

    @responses.activate
    def test_list_comparison_loads_rule_with_http_template_in_list_search_base_path(self):
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
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla",
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        assert _get_static_set_entries(processor.rules[0], "bad_users.list") == {
            "Franz",
            "Heinz",
            "Hans",
        }

    @pytest.mark.parametrize(
        ("json_content", "content_field"),
        [
            pytest.param(["Franz", "Heinz", "Hans"], ""),
            pytest.param(["Franz", "Heinz", "Hans"], None),
            pytest.param(
                ["Franz", "Heinz", "Hans"], NOT_SET, id="no_content_field_entry_in_config"
            ),
            pytest.param({"content": ["Franz", "Heinz", "Hans"]}, "content"),
            pytest.param({"_": ["Franz", "Heinz", "Hans"]}, "_"),
        ],
    )
    @responses.activate
    def test_list_comparison_loads_json_list_from_http(self, json_content, content_field):
        url = "http://localhost:8080/v2/valuestore/test_4"
        responses.add(
            responses.GET,
            url,
            json.dumps(json_content),
            content_type="application/json",
        )
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["bad_users.list"],
            },
        }

        if content_field is not NOT_SET:
            rule_dict["list_comparison"] |= {"content_field": content_field}

        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost:8080/v2/valuestore/test_4",
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        assert _get_static_set_entries(processor.rules[0], "bad_users.list") == {
            "Franz",
            "Heinz",
            "Hans",
        }

    @pytest.mark.parametrize(
        ("json_content", "content_field"),
        [
            pytest.param(["Franz", "Heinz", "Hans"], ""),
            pytest.param(["Franz", "Heinz", "Hans"], None),
            pytest.param(
                ["Franz", "Heinz", "Hans"], NOT_SET, id="no_content_field_entry_in_config"
            ),
            pytest.param({"content": ["Franz", "Heinz", "Hans"]}, "content"),
            pytest.param({"_": ["Franz", "Heinz", "Hans"]}, "_"),
        ],
    )
    def test_list_comparison_loads_json_list_from_file(self, json_content, content_field, tmp_path):
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
            },
        }

        if content_field is not NOT_SET:
            rule_dict["list_comparison"] |= {"content_field": content_field}

        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": str(file_root_path),
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        assert _get_static_set_entries(processor.rules[0], "file.json") == {
            "Franz",
            "Heinz",
            "Hans",
        }

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
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": str(file_root_path),
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        with pytest.raises(ValueError, match="Content is not a list"):
            processor.setup()

    @responses.activate
    def test_list_comparison_loads_rule_using_http_and_updates_with_callback(self, tmp_path):
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
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla",
        }

        RefreshableGetter.reset()

        getter_file_content = {url: {"refresh_interval": 10}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            processor = Factory.create({"custom_lister": config})
            rule = processor.rule_class.create_from_dict(rule_dict)
            processor._rule_tree.add_rule(rule)
            processor.setup()
            assert _get_static_set_entries(processor.rules[0], "bad_users.list") == {
                "Franz",
                "Heinz",
                "Hans",
            }
            HttpGetter(target=url, protocol="http").scheduler.run_all()
            assert _get_static_set_entries(processor.rules[0], "bad_users.list") == {
                "Franz",
                "Heinz",
            }

    @responses.activate
    def test_list_comparison_resolves_dynamic_http_template_from_event(self):
        document = {"tenant": "acme", "user": "Foo"}
        url_template = "http://localhost/${tenant}/${LOGPREP_LIST}"
        list_name = "bad_users.list"
        url = "http://localhost/acme/bad_users.list"
        expected = {
            "tenant": "acme",
            "user": "Foo",
            "user_results": {"in_list": [list_name]},
        }

        responses.add(responses.GET, url=url, body="Foo\nBar\n", status=200)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_name],
            },
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        processor.setup()
        assert _get_first_dynamic_set_entries(rule, list_name) is None
        assert len(responses.calls) == 0

        processor.process(document)

        assert document == expected
        assert _get_first_dynamic_set_entries(rule, list_name) == {"Foo", "Bar"}
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

    @pytest.mark.parametrize(
        "list_path, environment",
        [
            pytest.param("${tenant.id}/bad_users.list", {}, id="event-field"),
            pytest.param(
                "${LIST_TENANT}/${tenant.id}/bad_users.list",
                {"LIST_TENANT": "customers"},
                id="environment-and-event-field",
            ),
        ],
    )
    @responses.activate
    def test_list_comparison_resolves_dynamic_template_in_list_file_path(
        self, list_path, environment
    ):
        document = {"tenant": {"id": "acme"}, "user": "Foo"}
        path_prefix = "customers/" if environment else ""
        url = f"http://localhost/{path_prefix}acme/bad_users.list"
        responses.add(responses.GET, url=url, body="Foo\nBar\n", status=200)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_path],
            },
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/${LOGPREP_LIST}",
        }

        RefreshableGetter.reset()

        with mock_env(environment):
            processor = Factory.create({"custom_lister": config})
            rule = processor.rule_class.create_from_dict(rule_dict)
            processor._rule_tree.add_rule(rule)
            processor.setup()

            assert _get_first_dynamic_set_entries(rule, list_path) is None
            assert len(responses.calls) == 0

            processor.process(document)

        assert document["user_results"] == {"in_list": [url]}
        assert _get_first_dynamic_set_entries(rule, url) == {"Foo", "Bar"}
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

    @responses.activate
    def test_list_comparison_resolves_environment_template_in_list_file_path_during_setup(self):
        url = "http://localhost/acme/bad_users.list"
        responses.add(responses.GET, url=url, body="Foo\nBar\n", status=200)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["${LIST_TENANT}/bad_users.list"],
            },
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/${LOGPREP_LIST}",
        }

        RefreshableGetter.reset()

        with mock_env({"LIST_TENANT": "acme"}):
            processor = Factory.create({"custom_lister": config})
            rule = processor.rule_class.create_from_dict(rule_dict)
            processor._rule_tree.add_rule(rule)
            processor.setup()

        assert _get_first_dynamic_set_entries(rule, url) == {"Foo", "Bar"}
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

    @responses.activate
    def test_list_comparison_loads_static_and_dynamic_list_file_paths_lazily(self):
        document = {"tenant": {"id": "acme"}, "user": "Foo"}
        static_url = "http://localhost/common.list"
        dynamic_url = "http://localhost/acme/bad_users.list"
        responses.add(responses.GET, url=static_url, body="Foo\n", status=200)
        responses.add(responses.GET, url=dynamic_url, body="Foo\nBar\n", status=200)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["common.list", "${tenant.id}/bad_users.list"],
            },
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/${LOGPREP_LIST}",
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()

        assert _get_first_dynamic_set_entries(rule, list_name) is None
        assert len(responses.calls) == 0

        processor.process(document)

        assert document["user_results"] == {"in_list": [static_url, dynamic_url]}
        assert rule.compare_sets == {
            static_url: {"Foo"},
            dynamic_url: {"Foo", "Bar"},
        }
        assert len(responses.calls) == 2

    @pytest.mark.parametrize(
        "document, url_template",
        [
            pytest.param(
                {"tenant": {"id": "acme"}, "user": "Foo"},
                "http://localhost/${tenant.id}/${LOGPREP_LIST}",
                id="nested-field",
            ),
            pytest.param(
                {"tenants": ["acme"], "user": "Foo"},
                "http://localhost/${tenants.0}/${LOGPREP_LIST}",
                id="list-index",
            ),
            pytest.param(
                {"tenants": ["beta", "acme"], "user": "Foo"},
                "http://localhost/${tenants.-1}/${LOGPREP_LIST}",
                id="negative-list-index",
            ),
            pytest.param(
                {"tenant.id": "acme", "user": "Foo"},
                r"http://localhost/${tenant\.id}/${LOGPREP_LIST}",
                id="escaped-dot",
            ),
            pytest.param(
                {r"tenant\.id": "acme", "user": "Foo"},
                r"http://localhost/${tenant\\\.id}/${LOGPREP_LIST}",
                id="escaped-backslash-and-dot",
            ),
        ],
    )
    @responses.activate
    def test_list_comparison_resolves_dynamic_http_template_with_field_syntax(
        self, document, url_template
    ):
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
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()

        assert _get_first_dynamic_set_entries(rule, list_name) is None
        assert len(responses.calls) == 0

        processor.process(document)

        assert document["user_results"] == {"in_list": [url]}
        assert _get_first_dynamic_set_entries(rule, url) == {"Foo", "Bar"}
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url

    @responses.activate
    def test_list_comparison_dynamic_http_template_rejects_non_scalar_slice_value(self):
        document = {"tenants": ["acme", "beta"], "user": "Foo"}
        expected = {
            **document,
            "tags": ["_list_comparison_failure"],
        }
        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": ["bad_users.list"],
            },
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/${tenants.0:2}/${LOGPREP_LIST}",
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()

        result = processor.process(document)

        assert document == expected
        assert len(result.warnings) == 1
        assert "value for list comparison field 'tenants.0:2' is not a scalar value" in str(
            result.warnings[0]
        )
        assert len(responses.calls) == 0

    @responses.activate
    def test_list_comparison_reuses_dynamic_http_compare_set_and_signals_activity(self):
        first_document = {"tenant": "acme", "user": "Foo"}
        second_document = {"tenant": "acme", "user": "Bar"}
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
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()

        with mock.patch("logprep.util.getter.time.monotonic", side_effect=[100.0, 125.0]):
            processor.process(first_document)
            assert HttpGetter._target_to_data_caches[url].last_called == 100.0

            processor.process(second_document)
            assert HttpGetter._target_to_data_caches[url].last_called == 125.0

        assert len(responses.calls) == 1
        assert first_document["user_results"] == {"in_list": [url]}
        assert second_document["user_results"] == {"in_list": [url]}

    @responses.activate
    def test_list_comparison_dynamic_not_in_list_uses_current_event_compare_set(self):
        first_document = {"tenant": "acme", "user": "Foo"}
        second_document = {"tenant": "beta", "user": "Missing"}
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
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()

        processor.process(first_document)
        processor.process(second_document)

        assert first_document["user_results"] == {"in_list": [first_url]}
        assert second_document == expected_second_document
        assert rule.compare_sets == {
            first_url: {"Foo"},
            second_url: {"Bar"},
        }

    @responses.activate
    def test_list_comparison_dynamic_empty_http_list_is_used_for_not_in_list(self):
        document = {"tenant": "acme", "user": "Foo"}
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
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()

        processor.process(document)

        assert document == expected
        assert _get_first_dynamic_set_entries(rule, url) == set()

    @responses.activate
    def test_list_comparison_dynamic_http_template_rejects_non_scalar_event_values(self):
        document = {"tenant": ["acme"], "user": "Foo"}
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
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/${tenant}/${LOGPREP_LIST}",
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()

        result = processor.process(document)

        assert document == expected
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert "value for list comparison field 'tenant' is not a scalar value" in str(
            result.warnings[0]
        )
        assert len(responses.calls) == 0

    @responses.activate
    def test_list_comparison_dynamic_http_template_adds_failure_tag_if_event_field_is_missing(self):
        document = {"user": "Foo"}
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
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": "http://localhost/${tenant}/${LOGPREP_LIST}",
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()

        result = processor.process(document)

        assert document == expected
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert "missing event field 'tenant' for dynamic list comparison path" in str(
            result.warnings[0]
        )
        assert len(responses.calls) == 0

    @responses.activate
    def test_list_comparison_dynamic_http_failure_does_not_mark_rule_failed(self):
        failed_document = {"tenant": "acme", "user": "Foo"}
        successful_document = {"tenant": "beta", "user": "Foo"}
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
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()

        result = processor.process(failed_document)

        assert failed_document == expected_failed_document
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], ProcessingWarning)
        assert rule.data_error is None
        assert failed_url not in rule.compare_sets
        assert len(HttpGetter._target_to_data_caches[failed_url].callbacks) == 0
        assert len(HttpGetter._target_to_data_caches[failed_url].cleanup_callbacks) == 0

        processor.process(successful_document)

        assert successful_document == expected_successful_document
        assert rule.data_error is None
        assert _get_first_dynamic_set_entries(rule, successful_url) == {"Foo"}

    @responses.activate
    def test_list_comparison_removes_timed_out_dynamic_compare_set(self):
        document = {"tenant": "acme", "user": "Foo"}
        url_template = "http://localhost/${tenant}/${LOGPREP_LIST}"
        list_name = "bad_users.list"
        url = "http://localhost/acme/bad_users.list"

        responses.add(responses.GET, url=url, body="Foo\n", status=200)

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_name],
            },
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()

        with mock.patch("logprep.util.getter.time.monotonic", return_value=100.0):
            processor.process(document)

        assert _get_first_dynamic_set_entries(rule, url) == {"Foo"}
        assert url in HttpGetter._target_to_data_caches

        with mock.patch("logprep.util.getter.time.monotonic", return_value=161.1):
            refresh_getters()

        assert url not in rule.compare_sets
        assert url not in HttpGetter._target_to_data_caches

    def test_list_comparison_does_not_add_duplicates_from_list_source(self):
        document = {"users": ["Franz", "Alpha"]}
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
        }
        self._load_rule(rule_dict)
        self.object.setup()
        self.object.process(document)
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
    def test_match_list_field(self, testcase, system, result):
        document = {"system": system}
        expected = {"system": system, "system_results": result}
        rule_dict = {
            "filter": "system",
            "list_comparison": {
                "source_fields": ["system"],
                "target_field": "system_results",
                "list_file_paths": ["../lists/system_list.txt"],
            },
        }
        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": self.CONFIG["list_search_base_path"],
        }
        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)
        processor.setup()
        processor.process(document)
        assert document == expected, testcase

    @pytest.mark.parametrize(
        "http_list_content, expected_result",
        [
            ("", set()),
            ("\n", {""}),
        ],
    )
    @responses.activate
    def test_list_comparison_empty_http_list_or_empty_line_updates_compare_sets(
        self,
        http_list_content,
        expected_result,
    ):
        document = {"user": "Foo"}
        url_template = "http://localhost/tests/testdata/${LOGPREP_LIST}?ref=bla"
        list_name = "bad_users.list"
        url = Template(url_template).substitute({"LOGPREP_LIST": list_name})
        expected_document = {"user": "Foo", "user_results": {"not_in_list": [url]}}

        responses.add(
            responses.GET,
            url=url,
            body=http_list_content,
            status=200,
        )

        rule_dict = {
            "filter": "user",
            "list_comparison": {
                "source_fields": ["user"],
                "target_field": "user_results",
                "list_file_paths": [list_name],
            },
        }

        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        processor.setup()
        processor.process(document)

        assert document == expected_document
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == url
        assert rule.compare_sets[url] == expected_result

    @responses.activate
    def test_list_comparison_process_adds_failure_tag_if_http_list_returns_500(
        self,
        caplog,
    ):
        document = {"user": "Foo"}
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
        }

        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

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

        data_error = rule.data_error
        assert isinstance(data_error, RefreshableGetterError)

        assert captured_sessions

        session = captured_sessions[0]
        adapter = session.get_adapter(url)
        retries = adapter.max_retries

        assert retries.total == 3
        assert 500 in retries.status_forcelist

        assert "Caused by ResponseError('too many 500 error responses'))" in caplog.text
        assert "ListComparisonRule failed" in caplog.text

        processor.process(document)

        assert document == expected
        assert len(responses.calls) == retries.total + 1
        assert responses.calls[0].request.url == url
        assert _get_first_dynamic_set_entries(rule, list_name) is None

    @responses.activate
    def test_list_comparison_recovers_after_failed_http_getter_setup(
        self,
    ):
        document = {"user": "Foo"}
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
        }

        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        processor.setup()
        processor.process(document)

        data_error = rule.data_error
        assert isinstance(data_error, RefreshableGetterError)
        assert document == expected_failed_document
        assert _get_first_dynamic_set_entries(rule, list_name) is None
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
        expected_recovered_document = {
            "user": "Foo",
            "user_results": {"in_list": [url]},
        }

        RefreshableGetter.reset()

        processor = Factory.create({"custom_lister": config})
        rule = processor.rule_class.create_from_dict(rule_dict)
        processor._rule_tree.add_rule(rule)

        processor.setup()
        processor.process(document)

        assert rule.data_error is None
        assert document == expected_recovered_document
        assert _get_first_dynamic_set_entries(rule, url) == {"Foo"}
        assert responses.calls[-1].request.url == url
        assert responses.calls[-1].response.status_code == 200

    @responses.activate
    def test_list_comparison_recovers_after_failed_http_getter_while_processing(
        self,
        tmp_path,
    ):
        document = {"user": "Foo"}
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
        }

        config = {
            "type": "list_comparison",
            "rules": [],
            "list_search_base_path": url_template,
        }

        RefreshableGetter.reset()

        getter_file_content = {url: {"refresh_interval": 1}}
        http_getter_conf: Path = tmp_path / "http_getter.json"
        http_getter_conf.write_text(json.dumps(getter_file_content))
        with mock_env({ENV_NAME_LOGPREP_GETTER_CONFIG: str(http_getter_conf)}):
            processor = Factory.create({"custom_lister": config})
            rule = processor.rule_class.create_from_dict(rule_dict)
            processor._rule_tree.add_rule(rule)

            processor.setup()
            processor.process(document)

            data_error = rule.data_error
            assert isinstance(data_error, RefreshableGetterError)
            assert document == expected_failed_document
            assert _get_first_dynamic_set_entries(rule, list_name) is None
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
