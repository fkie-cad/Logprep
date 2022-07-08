# pylint: disable=protected-access
# pylint: disable=missing-docstring

import pytest

from logprep.processor.base.exceptions import ProcessingWarning
from logprep.processor.domain_label_extractor.processor import DuplicationError
from logprep.processor.processor_factory import ProcessorFactory
from tests.unit.processor.base import BaseProcessorTestCase


class TestDomainLabelExtractor(BaseProcessorTestCase):

    CONFIG = {
        "type": "domain_label_extractor",
        "generic_rules": ["tests/testdata/unit/domain_label_extractor/rules/generic"],
        "specific_rules": ["tests/testdata/unit/domain_label_extractor/rules/specific"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @property
    def generic_rules_dirs(self):
        return self.CONFIG.get("generic_rules")

    @property
    def specific_rules_dirs(self):
        return self.CONFIG.get("specific_rules")

    def test_events_processed_count(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"foo": "bar"}
        for i in range(1, 11):
            try:
                self.object.process(document)
            except ProcessingWarning:
                pass
            assert self.object.metrics.number_of_processed_events == i

    def test_domain_extraction_from_full_url(self):
        document = {"url": {"domain": "https://url.full.domain.de/path/file?param=1"}}
        expected_output = {
            "url": {
                "domain": "https://url.full.domain.de/path/file?param=1",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "url.full",
            }
        }
        self.object.process(document)

        assert document == expected_output

    def test_domain_extraction_to_existing_field(self):
        document = {"url": {"domain": "www.test.domain.de"}}
        expected_output = {
            "url": {
                "domain": "www.test.domain.de",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "www.test",
            }
        }
        self.object.process(document)

        assert document == expected_output

    def test_domain_extraction_to_new_dotted_subfield(self):
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
        self.object.process(document)

        assert document == expected_output

    def test_domain_extraction_without_subdomain(self):
        document = {"url": {"domain": "domain.de"}}
        expected_output = {
            "url": {
                "domain": "domain.de",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "",
            }
        }
        self.object.process(document)

        assert document == expected_output

    def test_domain_extraction_without_recognized_tld(self):
        document = {"url": {"domain": "domain.fubarbo"}}
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "tags": ["invalid_domain_in_url_domain"],
        }

        self.object.process(document)
        assert document == expected_output

    def test_domain_extraction_without_recognized_tld_with_existing_tag_field(self):
        document = {"url": {"domain": "domain.fubarbo"}, "tags": ["source"]}
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "tags": ["source", "invalid_domain_in_url_domain"],
        }

        self.object.process(document)
        assert document == expected_output

    def test_two_invalid_domains(self):
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

        self.object.process(document)
        assert document == expected_output

    def test_two_domains_one_is_invalid(self):
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

        self.object.process(document)
        assert document == expected_output

    def test_two_domains_one_is_invalid_one_has_ip(self):
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

        self.object.process(document)
        assert document == expected_output

    def test_new_non_default_tagging_field(self):
        config = {
            "Test DomainLabelExtractor Name": {
                "type": "domain_label_extractor",
                "generic_rules": ["tests/testdata/unit/domain_label_extractor/rules/generic"],
                "specific_rules": ["tests/testdata/unit/domain_label_extractor/rules/specific"],
                "tagging_field_name": "special_tags",
                "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            }
        }

        domain_label_extractor = ProcessorFactory.create(configuration=config, logger=self.logger)
        document = {"url": {"domain": "domain.fubarbo"}}
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "special_tags": ["invalid_domain_in_url_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_append_to_non_default_tagging_field(self):
        config = {
            "Test DomainLabelExtractor Name": {
                "type": "domain_label_extractor",
                "generic_rules": ["tests/testdata/unit/domain_label_extractor/rules/generic"],
                "specific_rules": ["tests/testdata/unit/domain_label_extractor/rules/specific"],
                "tagging_field_name": "special_tags",
                "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            }
        }

        domain_label_extractor = ProcessorFactory.create(config, self.logger)
        document = {"url": {"domain": "domain.fubarbo"}, "special_tags": ["source"]}
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "special_tags": ["source", "invalid_domain_in_url_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_domain_extraction_with_separated_tld(self):
        document = {"url": {"domain": "domain.co.uk"}}
        expected_output = {
            "url": {
                "domain": "domain.co.uk",
                "registered_domain": "domain.co.uk",
                "top_level_domain": "co.uk",
                "subdomain": "",
            }
        }
        self.object.process(document)

        assert document == expected_output

    def test_domain_extraction_with_ipv4_target(self):
        document = {"url": {"domain": "123.123.123.123"}}
        expected_output = {"url": {"domain": "123.123.123.123"}, "tags": ["ip_in_url_domain"]}

        self.object.process(document)
        assert document == expected_output

    def test_domain_extraction_with_ipv6_target(self):
        document = {"url": {"domain": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"}}
        expected_output = {
            "url": {"domain": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"},
            "tags": ["ip_in_url_domain"],
        }

        self.object.process(document)
        assert document == expected_output

    def test_domain_extraction_with_existing_output_field(self):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}

        with pytest.raises(
            DuplicationError,
            match=r"DomainLabelExtractor \(Test Instance Name\): The "
            r"following fields already existed and were not overwritten by the "
            r"DomainLabelExtractor: url\.subdomain",
        ):
            self.object.process(document)
