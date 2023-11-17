# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=line-too-long
# pylint: disable=too-many-statements
import pytest

from logprep.filter.expression.filter_expression import StringFilterExpression, Not, Exists
from logprep.framework.rule_tree.rule_parser import RuleParser
from logprep.processor.pre_detector.rule import PreDetectorRule

pytest.importorskip("logprep.processor.pre_detector")

string_filter_expression_1 = StringFilterExpression(["key1"], "value1")
string_filter_expression_2 = StringFilterExpression(["key2"], "value2")
string_filter_expression_3 = StringFilterExpression(["key3"], "value3")
string_filter_expression_4 = StringFilterExpression(["key4"], "value4")
string_filter_expression_with_subkey = StringFilterExpression(["key5", "subkey5"], "value5")


class TestRuleParser:
    @pytest.mark.parametrize(
        "rule, priority_dict, tag_map, expected_expressions",
        [
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "foo: bar",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [[Exists(["foo"]), StringFilterExpression(["foo"], "bar")]],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "foo: bar AND bar: foo",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [
                        Exists(["bar"]),
                        StringFilterExpression(["bar"], "foo"),
                        Exists(["foo"]),
                        StringFilterExpression(["foo"], "bar"),
                    ]
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "foo: bar OR bar: foo",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [Exists(["foo"]), StringFilterExpression(["foo"], "bar")],
                    [Exists(["bar"]), StringFilterExpression(["bar"], "foo")],
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "winlog: 123 AND test: (Good OR Okay OR Bad) OR foo: bar",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [
                        Exists(["test"]),
                        StringFilterExpression(["test"], "Good"),
                        Exists(["winlog"]),
                        StringFilterExpression(["winlog"], "123"),
                    ],
                    [
                        Exists(["test"]),
                        StringFilterExpression(["test"], "Okay"),
                        Exists(["winlog"]),
                        StringFilterExpression(["winlog"], "123"),
                    ],
                    [
                        Exists(["test"]),
                        StringFilterExpression(["test"], "Bad"),
                        Exists(["winlog"]),
                        StringFilterExpression(["winlog"], "123"),
                    ],
                    [Exists(["foo"]), StringFilterExpression(["foo"], "bar")],
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "(EventID: 1 AND ABC AND foo: bar)",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [
                        Exists(["ABC"]),
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "1"),
                        Exists(["foo"]),
                        StringFilterExpression(["foo"], "bar"),
                    ]
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "(EventID: 17 AND PipeName: \\PSHost*) AND NOT (Image: *\\powershell.exe)",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "17"),
                        Not(StringFilterExpression(["Image"], "*\\powershell.exe")),
                        Exists(["PipeName"]),
                        StringFilterExpression(["PipeName"], "\\PSHost*"),
                    ]
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "EventID: (17 OR 18) AND PipeName: (atctl OR userpipe OR iehelper)",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "17"),
                        Exists(["PipeName"]),
                        StringFilterExpression(["PipeName"], "atctl"),
                    ],
                    [
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "17"),
                        Exists(["PipeName"]),
                        StringFilterExpression(["PipeName"], "userpipe"),
                    ],
                    [
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "17"),
                        Exists(["PipeName"]),
                        StringFilterExpression(["PipeName"], "iehelper"),
                    ],
                    [
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "18"),
                        Exists(["PipeName"]),
                        StringFilterExpression(["PipeName"], "atctl"),
                    ],
                    [
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "18"),
                        Exists(["PipeName"]),
                        StringFilterExpression(["PipeName"], "userpipe"),
                    ],
                    [
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "18"),
                        Exists(["PipeName"]),
                        StringFilterExpression(["PipeName"], "iehelper"),
                    ],
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "EventID: 8 AND "
                        "SourceImage: (*System32cscript.exe OR *System32wscript.exe OR *System32mshta.exe) AND "
                        "TargetImage: *SysWOW64\\* AND NOT StartModule",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "8"),
                        Exists(["SourceImage"]),
                        StringFilterExpression(["SourceImage"], "*System32cscript.exe"),
                        Not(Exists(["StartModule"])),
                        Exists(["TargetImage"]),
                        StringFilterExpression(["TargetImage"], "*SysWOW64\\*"),
                    ],
                    [
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "8"),
                        Exists(["SourceImage"]),
                        StringFilterExpression(["SourceImage"], "*System32wscript.exe"),
                        Not(Exists(["StartModule"])),
                        Exists(["TargetImage"]),
                        StringFilterExpression(["TargetImage"], "*SysWOW64\\*"),
                    ],
                    [
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "8"),
                        Exists(["SourceImage"]),
                        StringFilterExpression(["SourceImage"], "*System32mshta.exe"),
                        Not(Exists(["StartModule"])),
                        Exists(["TargetImage"]),
                        StringFilterExpression(["TargetImage"], "*SysWOW64\\*"),
                    ],
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "bar: foo AND NOT foo: bar",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [
                        Exists(["bar"]),
                        StringFilterExpression(["bar"], "foo"),
                        Not(StringFilterExpression(["foo"], "bar")),
                    ]
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "winlog.event_id: 7036 AND NOT Something",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [
                        Not(Exists(["Something"])),
                        Exists(["winlog", "event_id"]),
                        StringFilterExpression(["winlog", "event_id"], "7036"),
                    ]
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "NOT (foo: bar AND (test: ok OR msg: (123 OR 456)))",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [Not(StringFilterExpression(["foo"], "bar"))],
                    [
                        Not(StringFilterExpression(["msg"], "123")),
                        Not(StringFilterExpression(["msg"], "456")),
                        Not(StringFilterExpression(["test"], "ok")),
                    ],
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "process.parent: (foo OR bar) AND process.executable: cmd.exe AND process.command_line: (perl OR python)",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [
                        Exists(["process", "command_line"]),
                        StringFilterExpression(["process", "command_line"], "perl"),
                        Exists(["process", "executable"]),
                        StringFilterExpression(["process", "executable"], "cmd.exe"),
                        Exists(["process", "parent"]),
                        StringFilterExpression(["process", "parent"], "foo"),
                    ],
                    [
                        Exists(["process", "command_line"]),
                        StringFilterExpression(["process", "command_line"], "python"),
                        Exists(["process", "executable"]),
                        StringFilterExpression(["process", "executable"], "cmd.exe"),
                        Exists(["process", "parent"]),
                        StringFilterExpression(["process", "parent"], "foo"),
                    ],
                    [
                        Exists(["process", "command_line"]),
                        StringFilterExpression(["process", "command_line"], "perl"),
                        Exists(["process", "executable"]),
                        StringFilterExpression(["process", "executable"], "cmd.exe"),
                        Exists(["process", "parent"]),
                        StringFilterExpression(["process", "parent"], "bar"),
                    ],
                    [
                        Exists(["process", "command_line"]),
                        StringFilterExpression(["process", "command_line"], "python"),
                        Exists(["process", "executable"]),
                        StringFilterExpression(["process", "executable"], "cmd.exe"),
                        Exists(["process", "parent"]),
                        StringFilterExpression(["process", "parent"], "bar"),
                    ],
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "EventID: 15 AND NOT (Imphash: 000 OR NOT AImphash)",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [
                        Not(Not(Exists(["AImphash"]))),
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "15"),
                        Not(StringFilterExpression(["Imphash"], "000")),
                    ]
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "(A1 OR A2) AND (B1 OR B2) AND (C1 OR C2) AND (D1 OR D2)",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [Exists(["A1"]), Exists(["B1"]), Exists(["C1"]), Exists(["D1"])],
                    [Exists(["A1"]), Exists(["B1"]), Exists(["C1"]), Exists(["D2"])],
                    [Exists(["A1"]), Exists(["B1"]), Exists(["C2"]), Exists(["D1"])],
                    [Exists(["A1"]), Exists(["B1"]), Exists(["C2"]), Exists(["D2"])],
                    [Exists(["A1"]), Exists(["B2"]), Exists(["C1"]), Exists(["D1"])],
                    [Exists(["A1"]), Exists(["B2"]), Exists(["C1"]), Exists(["D2"])],
                    [Exists(["A1"]), Exists(["B2"]), Exists(["C2"]), Exists(["D1"])],
                    [Exists(["A1"]), Exists(["B2"]), Exists(["C2"]), Exists(["D2"])],
                    [Exists(["A2"]), Exists(["B1"]), Exists(["C1"]), Exists(["D1"])],
                    [Exists(["A2"]), Exists(["B1"]), Exists(["C1"]), Exists(["D2"])],
                    [Exists(["A2"]), Exists(["B1"]), Exists(["C2"]), Exists(["D1"])],
                    [Exists(["A2"]), Exists(["B1"]), Exists(["C2"]), Exists(["D2"])],
                    [Exists(["A2"]), Exists(["B2"]), Exists(["C1"]), Exists(["D1"])],
                    [Exists(["A2"]), Exists(["B2"]), Exists(["C1"]), Exists(["D2"])],
                    [Exists(["A2"]), Exists(["B2"]), Exists(["C2"]), Exists(["D1"])],
                    [Exists(["A2"]), Exists(["B2"]), Exists(["C2"]), Exists(["D2"])],
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "(A1 OR A2) AND (B1 OR (C1 AND C2))",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [Exists(["A1"]), Exists(["B1"])],
                    [Exists(["A1"]), Exists(["C1"]), Exists(["C2"])],
                    [Exists(["A2"]), Exists(["B1"])],
                    [Exists(["A2"]), Exists(["C1"]), Exists(["C2"])],
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "((A1 OR A2) AND (B1 OR B2)) AND C1",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                [
                    [Exists(["A1"]), Exists(["B1"]), Exists(["C1"])],
                    [Exists(["A1"]), Exists(["B2"]), Exists(["C1"])],
                    [Exists(["A2"]), Exists(["B1"]), Exists(["C1"])],
                    [Exists(["A2"]), Exists(["B2"]), Exists(["C1"])],
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "winlog.channel: Security AND "
                        "winlog.event_id: 4625 AND "
                        "NOT ((winlog.channel: Security AND "
                        "(winlog.event_data.IpAddress: *-* OR winlog.event_data.IpAddress: (10.* OR 192.168.*) "
                        "OR "
                        "winlog.event_data.IpAddress: 1 "
                        "OR "
                        "winlog.event_data.IpAddress: (fe80* OR fc00*))))",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {},
                None,
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "(EventID: 12 AND TargetObject: *cmmgr32.exe*) "
                        "OR (EventID: 13 AND TargetObject: *cmmgr32.exe*) "
                        "OR (EventID: 10 AND CallTrace: *cmlua.dll*)",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {"EventID": "1"},
                {"TargetObject": "TAG", "CallTrace": "Key.subkey:Value"},
                [
                    [
                        Exists(["TAG"]),
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "12"),
                        Exists(["TargetObject"]),
                        StringFilterExpression(["TargetObject"], "*cmmgr32.exe*"),
                    ],
                    [
                        Exists(["TAG"]),
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "13"),
                        Exists(["TargetObject"]),
                        StringFilterExpression(["TargetObject"], "*cmmgr32.exe*"),
                    ],
                    [
                        StringFilterExpression(["Key", "subkey"], "Value"),
                        Exists(["EventID"]),
                        StringFilterExpression(["EventID"], "10"),
                        Exists(["CallTrace"]),
                        StringFilterExpression(["CallTrace"], "*cmlua.dll*"),
                    ],
                ],
            ),
            (
                PreDetectorRule._create_from_dict(
                    {
                        "filter": "NOT bar",
                        "pre_detector": {
                            "id": 1,
                            "title": "1",
                            "severity": "0",
                            "case_condition": "directly",
                            "mitre": [],
                        },
                    }
                ),
                {},
                {"bar": "tag"},
                [[Exists(["tag"]), Not(Exists(["bar"]))]],
            ),
        ],
    )
    def test_parse_rule_param(self, rule, priority_dict, tag_map, expected_expressions):
        rule_parser = RuleParser(tag_map)
        if expected_expressions is not None:
            assert rule_parser.parse_rule(rule, priority_dict) == expected_expressions
        else:
            assert rule_parser.parse_rule(rule, priority_dict)

    @pytest.mark.parametrize(
        "rule_list, expected",
        [
            (
                [
                    [
                        string_filter_expression_1,
                        string_filter_expression_2,
                        string_filter_expression_3,
                        string_filter_expression_4,
                    ]
                ],
                [
                    [
                        Exists(["key1"]),
                        string_filter_expression_1,
                        Exists(["key2"]),
                        string_filter_expression_2,
                        Exists(["key3"]),
                        string_filter_expression_3,
                        Exists(["key4"]),
                        string_filter_expression_4,
                    ]
                ],
            ),
            (
                [
                    [
                        string_filter_expression_1,
                        string_filter_expression_3,
                        string_filter_expression_with_subkey,
                    ]
                ],
                [
                    [
                        Exists(["key1"]),
                        string_filter_expression_1,
                        Exists(["key3"]),
                        string_filter_expression_3,
                        Exists(["key5", "subkey5"]),
                        string_filter_expression_with_subkey,
                    ]
                ],
            ),
            (
                [
                    [string_filter_expression_1],
                    [string_filter_expression_2],
                    [string_filter_expression_3],
                ],
                [
                    [Exists(["key1"]), string_filter_expression_1],
                    [Exists(["key2"]), string_filter_expression_2],
                    [Exists(["key3"]), string_filter_expression_3],
                ],
            ),
            ([[Not(string_filter_expression_1)]], [[Not(string_filter_expression_1)]]),
            (
                [[string_filter_expression_1, Exists(["key1"])], [string_filter_expression_1]],
                [
                    [string_filter_expression_1, Exists(["key1"])],
                    [Exists(["key1"]), string_filter_expression_1],
                ],
            ),
        ],
    )
    def test_add_exists_filter(self, rule_list, expected):
        RuleParser._add_exists_filter(rule_list)
        assert rule_list == expected
