# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments

import re
from copy import deepcopy

import pytest

from logprep.factory import Factory
from logprep.ng.event.log_event import LogEvent
from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from tests.unit.ng.processor.base import BaseProcessorTestCase
from tests.unit.processor.generic_adder.test_generic_adder import (
    failure_test_cases as non_ng_failure_test_cases,
)
from tests.unit.processor.generic_adder.test_generic_adder import (
    test_cases as non_ng_test_cases,
)

RULES_DIR_MISSING = "tests/testdata/unit/generic_adder/rules_missing"
RULES_DIR_INVALID = "tests/testdata/unit/generic_adder/rules_invalid"
RULES_DIR_FIRST_EXISTING = "tests/testdata/unit/generic_adder/rules_first_existing"


test_cases = deepcopy(non_ng_test_cases)
failure_test_cases = deepcopy(non_ng_failure_test_cases)


class TestGenericAdder(BaseProcessorTestCase):

    CONFIG = {
        "type": "ng_generic_adder",
        "rules": ["tests/testdata/unit/generic_adder/rules"],
    }

    @pytest.mark.parametrize("testcase, rule, event, expected", test_cases)
    def test_generic_adder_testcases(
        self, testcase, rule, event, expected
    ):  # pylint: disable=unused-argument
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"")
        self.object.process(log_event)
        assert event == expected

    @pytest.mark.parametrize("testcase, rule, event, expected, error_message", failure_test_cases)
    def test_generic_adder_testcases_failure_handling(
        self, testcase, rule, event, expected, error_message
    ):
        self._load_rule(rule)
        log_event = LogEvent(event, original=b"")
        result = self.object.process(log_event)
        assert len(result.warnings) == 1
        assert re.match(rf".*FieldExistsWarning.*{error_message}", str(result.warnings[0]))
        assert event == expected, testcase

    def test_add_generic_fields_from_file_missing_and_existing_with_all_required(self):
        with pytest.raises(InvalidRuleDefinitionError, match=r"files do not exist"):
            config = deepcopy(self.CONFIG)
            config["rules"] = [RULES_DIR_MISSING]
            configuration = {"test_instance_name": config}
            Factory.create(configuration)

    def test_add_generic_fields_from_file_invalid(self):
        with pytest.raises(
            InvalidRuleDefinitionError,
            match=r"must be a dictionary with string values",
        ):
            config = deepcopy(self.CONFIG)
            config["rules"] = [RULES_DIR_INVALID]
            configuration = {"test processor": config}
            Factory.create(configuration)
