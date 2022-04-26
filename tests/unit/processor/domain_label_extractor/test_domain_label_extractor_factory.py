# pylint: disable=protected-access
# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
import copy
from logging import getLogger
from pathlib import Path

import pytest

pytest.importorskip("logprep.processor.domain_label_extractor")


from logprep.processor.processor_factory_error import InvalidConfigurationError
from logprep.processor.domain_label_extractor.factory import DomainLabelExtractorFactory
from logprep.processor.domain_label_extractor.processor import (
    DomainLabelExtractor,
)

logger = getLogger()
REL_TLD_LIST_PATH = "tests/testdata/external/public_suffix_list.dat"
tld_list = f"file://{Path().absolute().joinpath(REL_TLD_LIST_PATH).as_posix()}"


class TestDomainLabelExtractorFactory:
    REQUIRED_CONFIG_FIELDS = {
        "type": "domain_label_extractor",
        "generic_rules": ["tests/testdata/unit/domain_label_extractor/rules/generic"],
        "specific_rules": ["tests/testdata/unit/domain_label_extractor/rules/specific"],
    }

    def test_create(self):
        assert isinstance(
            DomainLabelExtractorFactory.create("foo", self.REQUIRED_CONFIG_FIELDS, logger),
            DomainLabelExtractor,
        )

    def test_check_configuration(self):
        DomainLabelExtractorFactory._check_configuration(self.REQUIRED_CONFIG_FIELDS)
        for i in range(len(self.REQUIRED_CONFIG_FIELDS)):
            cfg = copy.deepcopy(self.REQUIRED_CONFIG_FIELDS)
            cfg.pop(list(cfg)[i])
            with pytest.raises(InvalidConfigurationError):
                DomainLabelExtractorFactory._check_configuration(cfg)

    def test_check_configuration_with_tld_list(self):
        self.config = copy.deepcopy(self.REQUIRED_CONFIG_FIELDS)
        self.config["tld_lists"] = [tld_list]
        assert isinstance(
            DomainLabelExtractorFactory.create("foo", self.config, logger), DomainLabelExtractor
        )

    def test_check_configuration_with_non_default_tagging_field_name(self):
        self.config = copy.deepcopy(self.REQUIRED_CONFIG_FIELDS)
        self.config["tagging_field_name"] = "special_tags"
        extractor = DomainLabelExtractorFactory.create("foo", self.config, logger)
        assert isinstance(extractor, DomainLabelExtractor)
        assert extractor._tagging_field_name == self.config["tagging_field_name"]
