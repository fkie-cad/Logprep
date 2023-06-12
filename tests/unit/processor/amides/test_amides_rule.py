# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=missing-docstring
import pytest

from logprep.processor.amides.rule import AmidesRule


@pytest.fixture(name="default_rule_definition")
def fixture_default_rule_definition():
    return {
        "filter": "winlog.event_id: 1 AND winlog.provider_name: Microsoft-Windows-Sysmon",
        "amides": {
            "source_fields": ["process.command_line"],
            "target_field": "amides",
        },
        "description": "Description for Amides",
    }


class TestAmidesRule:
    @pytest.mark.parametrize(
        "testcase, other_rule_definition, is_equal",
        [
            (
                "Should equal as they are the same",
                {
                    "filter": "winlog.event_id: 1 AND winlog.provider_name: Microsoft-Windows-Sysmon",
                    "amides": {
                        "source_fields": ["process.command_line"],
                        "target_field": "amides",
                    },
                    "description": "Description for Amides",
                },
                True,
            ),
            (
                "Should not equal due to different filter values",
                {
                    "filter": "winlog.event_id: 12",
                    "amides": {
                        "source_fields": ["process.command_line"],
                        "target_field": "amides",
                    },
                    "description": "Description for Amides",
                },
                False,
            ),
            (
                "Should not equal due to different source fields",
                {
                    "filter": "winlog.event_id: 1 AND winlog.provider_name: Microsoft-Windows-Sysmon",
                    "amides": {
                        "source_fields": ["winlog.event_data.CommandLine"],
                        "target_field": "amides",
                    },
                    "description": "Description for Amides",
                },
                False,
            ),
            (
                "Should not equal because of different target fields",
                {
                    "filter": "winlog.event_id: 1 AND winlog.provider_name: Microsoft-Windows-Sysmon",
                    "amides": {
                        "source_fields": ["process.command_line"],
                        "target_field": "rule_attrs",
                    },
                    "description": "Description for Amides",
                },
                False,
            ),
        ],
    )
    def test_rules_equality(
        self, default_rule_definition, testcase, other_rule_definition, is_equal
    ):
        rule1 = AmidesRule._create_from_dict(default_rule_definition)
        rule2 = AmidesRule._create_from_dict(other_rule_definition)
        assert (rule1 == rule2) == is_equal, testcase
