import pytest

pytest.importorskip("logprep.processor.pre_detector")

from logprep.filter.expression.filter_expression import And, Or, StringFilterExpression, Not, Exists
from logprep.framework.rule_tree.rule_parser import RuleParser as RP
from logprep.processor.pre_detector.rule import PreDetectorRule

str1 = StringFilterExpression(["key1"], "value1")
str2 = StringFilterExpression(["key2"], "value2")
str3 = StringFilterExpression(["key3"], "value3")
str4 = StringFilterExpression(["key4"], "value4")
str5 = StringFilterExpression(["key5", "subkey5"], "value5")

ex1 = Exists(["ABC.def"])
ex2 = Exists(["xyz"])


class TestRuleParser:
    def test_parse_rule(self):
        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [[Exists(["foo"]), StringFilterExpression(["foo"], "bar")]]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
            [
                Exists(["bar"]),
                StringFilterExpression(["bar"], "foo"),
                Exists(["foo"]),
                StringFilterExpression(["foo"], "bar"),
            ]
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
            [Exists(["foo"]), StringFilterExpression(["foo"], "bar")],
            [Exists(["bar"]), StringFilterExpression(["bar"], "foo")],
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
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
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
            [
                Exists(["ABC"]),
                Exists(["EventID"]),
                StringFilterExpression(["EventID"], "1"),
                Exists(["foo"]),
                StringFilterExpression(["foo"], "bar"),
            ]
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
            [
                Exists(["EventID"]),
                StringFilterExpression(["EventID"], "17"),
                Not(StringFilterExpression(["Image"], "*\\powershell.exe")),
                Exists(["PipeName"]),
                StringFilterExpression(["PipeName"], "\\PSHost*"),
            ]
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
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
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
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
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(
            rule, {"EventID": "1"}, {"TargetObject": "TAG", "CallTrace": "Key.subkey:Value"}
        )
        assert parsed_rule == [
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
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
            [
                Exists(["bar"]),
                StringFilterExpression(["bar"], "foo"),
                Not(StringFilterExpression(["foo"], "bar")),
            ]
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        tag_map = {"bar": "tag"}
        parsed_rule = RP.parse_rule(rule, {}, tag_map)
        assert parsed_rule == [[Exists(["tag"]), Not(Exists(["bar"]))]]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
            [
                Not(Exists(["Something"])),
                Exists(["winlog", "event_id"]),
                StringFilterExpression(["winlog", "event_id"], "7036"),
            ]
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
            [Not(StringFilterExpression(["foo"], "bar"))],
            [
                Not(StringFilterExpression(["msg"], "123")),
                Not(StringFilterExpression(["msg"], "456")),
                Not(StringFilterExpression(["test"], "ok")),
            ],
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
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
        ]

        rule = PreDetectorRule._create_from_dict(
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
        )
        parsed_rule = RP.parse_rule(rule, {}, {})
        assert parsed_rule == [
            [
                Not(Not(Exists(["AImphash"]))),
                Exists(["EventID"]),
                StringFilterExpression(["EventID"], "15"),
                Not(StringFilterExpression(["Imphash"], "000")),
            ]
        ]

    def test_has_unresolved_not_expression(self):
        exp = And(str1, str2)
        assert not RP._has_unresolved_not_expression(exp)

        exp = Not(str1)
        assert not RP._has_unresolved_not_expression(exp)

        exp = And(Not(str1), str2)
        assert not RP._has_unresolved_not_expression(exp)

        exp = Or(And(str1, Not(str2)))
        assert not RP._has_unresolved_not_expression(exp)

        exp = Or(And(str1, str2))
        assert not RP._has_unresolved_not_expression(exp)

        exp = Not(And(str1, str2))
        assert RP._has_unresolved_not_expression(exp)

        exp = Or(Not(And(str1, str2)), str3)
        assert RP._has_unresolved_not_expression(exp)

    def test_parse_NOT(self):
        exp = Not(str1)
        assert RP._parse_not_expression(exp) == exp

        exp = Not(Or(str1, str2))
        assert RP._parse_not_expression(exp) == And(Not(str1), Not(str2))

        exp = Not(And(str1, str2))
        assert RP._parse_not_expression(exp) == Or(Not(str1), Not(str2))

        exp = And(Not(Or(str1, str2)), str3)
        assert RP._parse_not_expression(exp) == And(And(Not(str1), Not(str2)), str3)

        exp = Or(Not(Or(str1, str2)), str3)
        assert RP._parse_not_expression(exp) == Or(And(Not(str1), Not(str2)), str3)

        exp = Not(Or(And(str1, str2), str3))
        assert RP._parse_not_expression(exp) == And(Or(Not(str1), Not(str2)), Not(str3))

        exp = Not(And(Or(str1, str2), str3))
        assert RP._parse_not_expression(exp) == Or(And(Not(str1), Not(str2)), Not(str3))

        exp = And(Not(And(str1, str2)), str3)
        assert RP._parse_not_expression(exp) == And(Or(Not(str1), Not(str2)), str3)

        exp = And(Not(Or(str1, str2)), Not(And(str3, str4)))
        assert RP._parse_not_expression(exp) == And(
            And(Not(str1), Not(str2)), Or(Not(str3), Not(str4))
        )

    def test_parse_AND(self):
        exp = And(str1, str2)
        assert RP._parse_and_expression(exp) == [str1, str2]

        exp = And(str1, str2, str3)
        assert RP._parse_and_expression(exp) == [str1, str2, str3]

        exp = And(str1, Not(str2))
        assert RP._parse_and_expression(exp) == [str1, Not(str2)]

        exp = And(str1, And(Not(str2), str3))
        assert RP._parse_and_expression(exp) == [str1, Not(str2), str3]

    def test_parse_OR(self):
        exp = Or(str1, str2)
        assert RP._parse_or_expression(exp) == [[str1], [str2]]

        exp = And(str1, Or(str2, str3))
        assert RP._parse_or_expression(exp) == [[str1, str2], [str1, str3]]

        exp = And(str1, Or(str2, str3), str4)
        assert RP._parse_or_expression(exp) == [[str1, str4, str2], [str1, str4, str3]]

        exp = Or(And(Not(str1), Not(str2)), str3)
        assert RP._parse_or_expression(exp) == [[Not(str1), Not(str2)], [str3]]

        exp = And(Or(Not(str1), Not(str2)), Not(str3))
        assert RP._parse_or_expression(exp) == [[Not(str3), Not(str1)], [Not(str3), Not(str2)]]

        exp = And(Not(str1), Not(str2), Or(Not(str3), Not(str4)))
        assert RP._parse_or_expression(exp) == [
            [Not(str1), Not(str2), Not(str3)],
            [Not(str1), Not(str2), Not(str4)],
        ]

        exp = And(And(Not(str1), Not(str2)), Or(Not(str3), Not(str4)))
        assert RP._parse_or_expression(exp) == [
            [Not(str2), Not(str1), Not(str3)],
            [Not(str2), Not(str1), Not(str4)],
        ]

        exp = And(Or(str1, str2), Or(str3, str4))
        assert RP._parse_or_expression(exp) == [
            [str1, str3],
            [str1, str4],
            [str2, str3],
            [str2, str4],
        ]

        exp = Or(And(str1, Or(str2, str3)), str4)
        assert RP._parse_or_expression(exp) == [[str1, str2], [str1, str3], [str4]]

    def test_has_or_expression(self):
        exp = And(str1, str2)
        assert not RP._has_or_expression(exp)

        exp = Or(str1, str2)
        assert RP._has_or_expression(exp)

        exp = Not(str1)
        assert not RP._has_or_expression(exp)

        exp = Not(And(str1, str2))
        assert not RP._has_or_expression(exp)

        exp = Not(Or(str1, str2))
        assert RP._has_or_expression(exp)

        exp = And(Not(Or(str1, str2)))
        assert RP._has_or_expression(exp)

        exp = And(Not(And(str1, str2)))
        assert not RP._has_or_expression(exp)

    def test_sort_rule_segments(self):
        rule_list = [[str1, str4, str3, str2]]

        RP._sort_rule_segments(rule_list, {})

        assert rule_list == [[str1, str2, str3, str4]]

        rule_list = [[str1, str4, str3, str2]]
        priority_dict = {"key2": "1"}

        RP._sort_rule_segments(rule_list, priority_dict)

        assert rule_list == [[str2, str1, str3, str4]]

        rule_list = [[str1, str3, ex1, str2, ex2]]
        RP._sort_rule_segments(rule_list, {})

        assert rule_list == [[ex1, str1, str2, str3, ex2]]

        rule_list = [[str1, str3, ex1, str2, ex2]]
        priority_dict = {"xyz": "1"}
        RP._sort_rule_segments(rule_list, priority_dict)

        assert rule_list == [[ex2, ex1, str1, str2, str3]]

        rule_list = [[str2, Not(str1)]]
        priority_dict = {"key1": "1"}
        RP._sort_rule_segments(rule_list, priority_dict)

        assert rule_list == [[Not(str1), str2]]

    def test_add_special_tags(self):
        rule_list = [[str1, str2]]
        tag_map = {"key2": "TAG"}

        RP._add_special_tags(rule_list, tag_map)
        assert rule_list == [[Exists(["TAG"]), str1, str2]]

        rule_list = [[str1, str2], [str1, str3]]
        tag_map = {"key2": "TAG2", "key3": "TAG3"}

        RP._add_special_tags(rule_list, tag_map)
        assert rule_list == [[Exists(["TAG2"]), str1, str2], [Exists(["TAG3"]), str1, str3]]

        rule_list = [[str1, str4, str2], [str2, str3], [str2], [str4, str3]]
        tag_map = {"key1": "TAG1", "key2": "TAG2"}

        RP._add_special_tags(rule_list, tag_map)
        assert rule_list == [
            [Exists(["TAG2"]), Exists(["TAG1"]), str1, str4, str2],
            [Exists(["TAG2"]), str2, str3],
            [Exists(["TAG2"]), str2],
            [str4, str3],
        ]

        rule_list = [[str1, str3], [str2, str4]]
        tag_map = {"key1": "TAG1", "key2": "TAG2.SUBTAG2"}

        RP._add_special_tags(rule_list, tag_map)
        assert rule_list == [
            [Exists(["TAG1"]), str1, str3],
            [Exists(["TAG2", "SUBTAG2"]), str2, str4],
        ]

        rule_list = [[str1, str3], [str2, str4]]
        tag_map = {"key1": "TAG1:Value1", "key2": "TAG2.SUBTAG2"}

        RP._add_special_tags(rule_list, tag_map)
        assert rule_list == [
            [StringFilterExpression(["TAG1"], "Value1"), str1, str3],
            [Exists(["TAG2", "SUBTAG2"]), str2, str4],
        ]

        rule_list = [[str1, str3], [str2, str4]]
        tag_map = {"key1": "TAG1.SUBTAG1:Value1", "key2": "TAG2.SUBTAG2"}

        RP._add_special_tags(rule_list, tag_map)
        assert rule_list == [
            [StringFilterExpression(["TAG1", "SUBTAG1"], "Value1"), str1, str3],
            [Exists(["TAG2", "SUBTAG2"]), str2, str4],
        ]

        rule_list = [[str1, ex2]]
        tag_map = {"xyz": "TAG:VALUE"}

        RP._add_special_tags(rule_list, tag_map)
        assert rule_list == [[StringFilterExpression(["TAG"], "VALUE"), str1, ex2]]

        rule_list = [[Not(str1)]]
        tag_map = {"key1": "TAG"}

        RP._add_special_tags(rule_list, tag_map)
        assert rule_list == [[Exists(["TAG"]), Not(str1)]]

    def test_add_exists_filter(self):
        rule_list = [[str1, str2, str3, str4]]
        RP._add_exists_filter(rule_list)

        assert rule_list == [
            [
                Exists(["key1"]),
                str1,
                Exists(["key2"]),
                str2,
                Exists(["key3"]),
                str3,
                Exists(["key4"]),
                str4,
            ]
        ]

        rule_list = [[str1, str3, str5]]
        RP._add_exists_filter(rule_list)

        assert rule_list == [
            [Exists(["key1"]), str1, Exists(["key3"]), str3, Exists(["key5", "subkey5"]), str5]
        ]

        rule_list = [[str1], [str2], [str3]]
        RP._add_exists_filter(rule_list)

        assert rule_list == [
            [Exists(["key1"]), str1],
            [Exists(["key2"]), str2],
            [Exists(["key3"]), str3],
        ]

        rule_list = [[Not(str1)]]
        RP._add_exists_filter(rule_list)

        assert rule_list == [[Not(str1)]]
