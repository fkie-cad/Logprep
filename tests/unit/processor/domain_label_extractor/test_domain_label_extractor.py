import copy
from pathlib import Path
import pytest

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
rules_dir = "tests/testdata/unit/domain_label_extractor/rules/"
rel_tld_list_path = "tests/testdata/external/public_suffix_list.dat"
tld_list = f"file://{Path().absolute().joinpath(rel_tld_list_path).as_posix()}"


@pytest.fixture()
def domain_label_extractor():
    config = {
        "type": "domain_label_extractor",
        "rules": [rules_dir],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    domain_label_extractor = DomainLabelExtractorFactory.create(
        "Test DomainLabelExtractor Name", config, logger
    )
    return domain_label_extractor


class TestDomainLabelExtractor:
    @staticmethod
    def _load_specific_rule(domain_label_extractor, rule):
        specific_rule = DomainLabelExtractorRule._create_from_dict(rule)
        domain_label_extractor._specific_tree.add_rule(specific_rule, logger)

    def test_is_a_processor_implementation(self, domain_label_extractor):
        assert isinstance(domain_label_extractor, RuleBasedProcessor)

    def test_describe(self, domain_label_extractor):
        assert (
            domain_label_extractor.describe()
            == "DomainLabelExtractor (Test DomainLabelExtractor Name)"
        )

    def test_events_processed_count(self, domain_label_extractor):
        assert domain_label_extractor.ps.processed_count == 0
        document = {"foo": "bar"}
        for i in range(1, 11):
            try:
                domain_label_extractor.process(document)
            except ProcessingWarning:
                pass
            assert domain_label_extractor.ps.processed_count == i

    def test_domain_extraction_from_full_url(self, domain_label_extractor):
        document = {"url": {"domain": "https://url.full.domain.de/path/file?param=1"}}
        expected_output = {
            "url": {
                "domain": "https://url.full.domain.de/path/file?param=1",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "url.full",
            }
        }
        domain_label_extractor.process(document)

        assert document == expected_output

    def test_domain_extraction_to_existing_field(self, domain_label_extractor):
        document = {"url": {"domain": "www.test.domain.de"}}
        expected_output = {
            "url": {
                "domain": "www.test.domain.de",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "www.test",
            }
        }
        domain_label_extractor.process(document)

        assert document == expected_output

    def test_domain_extraction_to_new_dotted_subfield(self, domain_label_extractor):
        document = {"url2": {"domain": "www.test.domain.de"}}
        expected_output = {
            "url2": {"domain": "www.test.domain.de"},
            "extracted": {
                "domain": {
                    "info": {
                        "registered_domain": "domain.de",
                        "top_level_domain": "de",
                        "subdomain": "www.test",
                    }
                }
            },
        }
        domain_label_extractor.process(document)

        assert document == expected_output

    def test_domain_extraction_without_subdomain(self, domain_label_extractor):
        document = {"url": {"domain": "domain.de"}}
        expected_output = {
            "url": {
                "domain": "domain.de",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "",
            }
        }
        domain_label_extractor.process(document)

        assert document == expected_output

    def test_domain_extraction_without_recognized_tld(self, domain_label_extractor):
        document = {"url": {"domain": "domain.fubarbo"}}
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "tags": ["invalid_domain_in_url_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_domain_extraction_without_recognized_tld_with_existing_tag_field(
        self, domain_label_extractor
    ):
        document = {"url": {"domain": "domain.fubarbo"}, "tags": ["source"]}
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "tags": ["source", "invalid_domain_in_url_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_two_invalid_domains(self, domain_label_extractor):
        document = {
            "url": {"domain": "domain.fubarbo"},
            "source": {"domain": "domain.invalid"},
            "tags": ["source"],
        }
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "source": {"domain": "domain.invalid"},
            "tags": ["source", "invalid_domain_in_url_domain", "invalid_domain_in_source_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_two_domains_one_is_invalid(self, domain_label_extractor):
        document = {
            "url": {"domain": "domain.de"},
            "source": {"domain": "domain.invalid"},
            "tags": ["source"],
        }
        expected_output = {
            "url": {
                "domain": "domain.de",
                "registered_domain": "domain.de",
                "subdomain": "",
                "top_level_domain": "de",
            },
            "source": {"domain": "domain.invalid"},
            "tags": ["source", "invalid_domain_in_source_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_two_domains_one_is_invalid_one_has_ip(self, domain_label_extractor):
        document = {
            "url": {"domain": "domain.fubarbo"},
            "source": {"domain": "123.123.123.123"},
            "tags": ["source"],
        }
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "source": {"domain": "123.123.123.123"},
            "tags": ["source", "invalid_domain_in_url_domain", "ip_in_source_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_new_non_default_tagging_field(self):
        config = {
            "type": "domain_label_extractor",
            "rules": [rules_dir],
            "tagging_field_name": "special_tags",
            "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        }

        domain_label_extractor = DomainLabelExtractorFactory.create(
            "Test DomainLabelExtractor Name", config, logger
        )
        document = {"url": {"domain": "domain.fubarbo"}}
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "special_tags": ["invalid_domain_in_url_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_append_to_non_default_tagging_field(self):
        config = {
            "type": "domain_label_extractor",
            "rules": [rules_dir],
            "tagging_field_name": "special_tags",
            "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
        }

        domain_label_extractor = DomainLabelExtractorFactory.create(
            "Test DomainLabelExtractor Name", config, logger
        )
        document = {"url": {"domain": "domain.fubarbo"}, "special_tags": ["source"]}
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "special_tags": ["source", "invalid_domain_in_url_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_domain_extraction_with_separated_tld(self, domain_label_extractor):
        document = {"url": {"domain": "domain.co.uk"}}
        expected_output = {
            "url": {
                "domain": "domain.co.uk",
                "registered_domain": "domain.co.uk",
                "top_level_domain": "co.uk",
                "subdomain": "",
            }
        }
        domain_label_extractor.process(document)

        assert document == expected_output

    def test_domain_extraction_with_ipv4_target(self, domain_label_extractor):
        document = {"url": {"domain": "123.123.123.123"}}
        expected_output = {"url": {"domain": "123.123.123.123"}, "tags": ["ip_in_url_domain"]}

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_domain_extraction_with_ipv6_target(self, domain_label_extractor):
        document = {"url": {"domain": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"}}
        expected_output = {
            "url": {"domain": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"},
            "tags": ["ip_in_url_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_domain_extraction_with_existing_output_field(self, domain_label_extractor):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}

        with pytest.raises(
            DuplicationError,
            match=r"DomainLabelExtractor \(Test DomainLabelExtractor Name\): The "
            r"following fields already existed and were not overwritten by the "
            r"DomainLabelExtractor: url\.subdomain",
        ):
            domain_label_extractor.process(document)


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


class TestDomainLabelExtractorFactory:
    REQUIRED_CONFIG_FIELDS = {
        "type": "domain_label_extractor",
        "rules": [rules_dir],
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
