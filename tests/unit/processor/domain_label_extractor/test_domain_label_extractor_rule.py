import copy
from pathlib import Path
import pytest

from tests.unit.processor.base import BaseProcessorTestCase

pytest.importorskip("logprep.processor.domain_label_extractor")

from logging import getLogger

from logprep.processor.base.processor import RuleBasedProcessor, ProcessingWarning
from logprep.processor.processor_factory_error import InvalidConfigurationError
from logprep.processor.domain_label_extractor.rule import (
    DomainLabelExtractorRule,
    InvalidDomainLabelExtractorDefinition,
)
from logprep.processor.domain_label_extractor.factory import DomainLabelExtractorFactory
from logprep.processor.domain_label_extractor.processor import (
    DomainLabelExtractor,
    DuplicationError,
)

logger = getLogger()
rel_tld_list_path = "tests/testdata/external/public_suffix_list.dat"
tld_list = f"file://{Path().absolute().joinpath(rel_tld_list_path).as_posix()}"


class TestDomainLabelExtractorRule:

    RULE = {
        "filter": "url.domain",
        "domain_label_extractor": {"target_field": "url.domain", "output_field": "url"},
        "description": "insert a description text",
    }

    def test_valid_rule(self):
        DomainLabelExtractorRule._create_from_dict(self.RULE)

    def test_missing_target_field(self):
        rule = copy.deepcopy(self.RULE)
        del rule["domain_label_extractor"]["target_field"]

        with pytest.raises(
            InvalidDomainLabelExtractorDefinition,
            match=r"DomainLabelExtractor rule \(The following "
            r"DomainLabelExtractor definition is invalid: "
            r"Missing 'target_field' in rule "
            r"configuration\.\)",
        ):
            DomainLabelExtractorRule._create_from_dict(rule)

    def test_wrong_target_field_type(self):
        rule = copy.deepcopy(self.RULE)
        rule["domain_label_extractor"]["target_field"] = 123

        with pytest.raises(
            InvalidDomainLabelExtractorDefinition,
            match=r"DomainLabelExtractor definition is invalid: "
            r"'target_field' should be 'str' and not "
            r"'<class 'int'>'",
        ):
            DomainLabelExtractorRule._create_from_dict(rule)

    def test_missing_output_field(self):
        rule = copy.deepcopy(self.RULE)
        del rule["domain_label_extractor"]["output_field"]

        with pytest.raises(
            InvalidDomainLabelExtractorDefinition,
            match=r"DomainLabelExtractor rule \(The following "
            r"DomainLabelExtractor definition is invalid: "
            r"Missing 'output_field' in rule "
            r"configuration\.\)",
        ):
            DomainLabelExtractorRule._create_from_dict(rule)

    def test_wrong_output_field_type(self):
        rule = copy.deepcopy(self.RULE)
        rule["domain_label_extractor"]["output_field"] = 123

        with pytest.raises(
            InvalidDomainLabelExtractorDefinition,
            match=r"DomainLabelExtractor definition is invalid: "
            r"'output_field' should be 'str' and not "
            r"'<class 'int'>'",
        ):
            DomainLabelExtractorRule._create_from_dict(rule)
