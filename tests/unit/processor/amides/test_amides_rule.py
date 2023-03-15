# pylint: disable=protected-access
import pytest


from logprep.processor.amides.rule import AmidesRule


@pytest.fixture(name="default_rule_definition")
def fixture_default_rule_definition():
    return {
        "filter": "winlog.event_id: 1 AND winlog.provider_name: Microsoft-Windows-Sysmon",
        "amides": {
            "commandline_field": "process.command_line",
            "rule_attributions_field": "rule_attributions",
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
                        "commandline_field": "process.command_line",
                        "rule_attributions_field": "rule_attributions",
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
                        "commandline_field": "process.command_line",
                        "rule_attributions_field": "rule_attributions",
                    },
                    "description": "Description for Amides",
                },
                False,
            ),
            (
                "Should not equal due to different command line field",
                {
                    "filter": "winlog.event_id: 1 AND winlog.provider_name: Microsoft-Windows-Sysmon",
                    "amides": {
                        "commandline_field": "winlog.event_data.CommandLine",
                        "rule_attributions_field": "rule_attributions",
                    },
                    "description": "Description for Amides",
                },
                False,
            ),
            (
                "Should not equal because of different confidence values field",
                {
                    "filter": "winlog.event_id: 1 AND winlog.provider_name: Microsoft-Windows-Sysmon",
                    "amides": {
                        "commandline_field": "process.command_line",
                        "rule_attributions_field": "rule_attrs",
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
