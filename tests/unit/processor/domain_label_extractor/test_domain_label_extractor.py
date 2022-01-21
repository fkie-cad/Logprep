import copy
import pytest

pytest.importorskip('logprep.processor.domain_label_extractor')

from logging import getLogger

from logprep.processor.base.processor import RuleBasedProcessor, ProcessingWarning
from logprep.processor.processor_factory_error import InvalidConfigurationError
from logprep.processor.domain_label_extractor.rule import DomainLabelExtractorRule
from logprep.processor.domain_label_extractor.factory import DomainLabelExtractorFactory
from logprep.processor.domain_label_extractor.processor import UnrecognizedTldError, DomainLabelExtractor

logger = getLogger()
rules_dir = 'tests/testdata/unit/domain_label_extractor/rules/'


@pytest.fixture()
def domain_label_extractor():
    config = {
        'type': 'domain_label_extractor',
        'rules': [rules_dir],
        'tree_config': 'tests/testdata/unit/shared_data/tree_config.json'
    }

    domain_label_extractor = DomainLabelExtractorFactory.create('Test DomainLabelExtractor Name', config, logger)
    return domain_label_extractor


class TestDomainLabelExtractor:

    @staticmethod
    def _load_specific_rule(domain_label_extractor, rule):
        specific_rule = DomainLabelExtractorRule._create_from_dict(rule)
        domain_label_extractor._specific_tree.add_rule(specific_rule, logger)

    def test_is_a_processor_implementation(self, domain_label_extractor):
        assert isinstance(domain_label_extractor, RuleBasedProcessor)

    def test_describe(self, domain_label_extractor):
        assert domain_label_extractor.describe() == 'DomainLabelExtractor (Test DomainLabelExtractor Name)'

    def test_events_processed_count(self, domain_label_extractor):
        assert domain_label_extractor.events_processed_count() == 0
        document = {'foo': 'bar'}
        for i in range(1, 11):
            try:
                domain_label_extractor.process(document)
            except ProcessingWarning:
                pass
            assert domain_label_extractor.events_processed_count() == i

    def test_domain_extraction_from_full_url(self, domain_label_extractor):
        document = {'url': {'domain': 'https://url.full.domain.de/path/file?param=1'}}
        expected_output = {
            'url': {
                'domain': 'https://url.full.domain.de/path/file?param=1',
                'registered_domain': 'domain.de',
                'top_level_domain': 'de',
                'subdomain': 'url.full',
            }
        }
        domain_label_extractor.process(document)

        assert document == expected_output

    def test_domain_extraction_to_existing_field(self, domain_label_extractor):
        document = {'url': {'domain': 'www.test.domain.de'}}
        expected_output = {
            'url': {
                'domain': 'www.test.domain.de',
                'registered_domain': 'domain.de',
                'top_level_domain': 'de',
                'subdomain': 'www.test',
            }
        }
        domain_label_extractor.process(document)

        assert document == expected_output

    def test_domain_extraction_to_new_dotted_subfield(self, domain_label_extractor):
        document = {'url2': {'domain': 'www.test.domain.de'}}
        expected_output = {
            'url2': {'domain': 'www.test.domain.de'},
            'extracted': {
                'domain': {
                    'info': {
                        'registered_domain': 'domain.de',
                        'top_level_domain': 'de',
                        'subdomain': 'www.test',
                    }
                }
            }
        }
        domain_label_extractor.process(document)

        assert document == expected_output

    def test_domain_extraction_without_subdomain(self, domain_label_extractor):
        document = {'url': {'domain': 'domain.de'}}
        expected_output = {
            'url': {
                'domain': 'domain.de',
                'registered_domain': 'domain.de',
                'top_level_domain': 'de',
                'subdomain': '',
            }
        }
        domain_label_extractor.process(document)

        assert document == expected_output

    def test_domain_extraction_without_recognized_tld(self, domain_label_extractor):
        document = {'url': {'domain': 'domain.fubarbo'}}

        with pytest.raises(UnrecognizedTldError):
            domain_label_extractor.process(document)

    def test_domain_extraction_with_separated_tld(self, domain_label_extractor):
        document = {'url': {'domain': 'domain.co.uk'}}
        expected_output = {
            'url': {
                'domain': 'domain.co.uk',
                'registered_domain': 'domain.co.uk',
                'top_level_domain': 'co.uk',
                'subdomain': '',
            }
        }
        domain_label_extractor.process(document)

        assert document == expected_output


class TestDomainLabelExtractorFactory:
    VALID_CONFIG = {
        'type': 'domain_label_extractor',
        'rules': [rules_dir]
    }

    def test_create(self):
        assert isinstance(DomainLabelExtractorFactory.create('foo', self.VALID_CONFIG, logger), DomainLabelExtractor)

    def test_check_configuration(self):
        DomainLabelExtractorFactory._check_configuration(self.VALID_CONFIG)
        for i in range(len(self.VALID_CONFIG)):
            cfg = copy.deepcopy(self.VALID_CONFIG)
            cfg.pop(list(cfg)[i])
            with pytest.raises(InvalidConfigurationError):
                DomainLabelExtractorFactory._check_configuration(cfg)
