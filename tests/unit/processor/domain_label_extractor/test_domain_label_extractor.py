# pylint: disable=protected-access
# pylint: disable=missing-docstring


from copy import deepcopy

import pytest

from logprep.factory import Factory
from logprep.processor.base.exceptions import (
    FieldExistsWarning,
    ProcessingCriticalError,
)
from tests.unit.processor.base import BaseProcessorTestCase

TEST_RULE = {
    "filter": "url",
    "domain_label_extractor": {"source_fields": ["url.domain"], "target_field": "url"},
    "description": "",
}

test_cases = [
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "https://url.full.domain.de/path/file?param=1"}},
        {
            "url": {
                "domain": "https://url.full.domain.de/path/file?param=1",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "url.full",
            }
        },
        id="extraction from full url",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "/path/file?param=1"}},
        {
            "url": {
                "domain": "/path/file?param=1",
                "registered_domain": "",
                "subdomain": "",
                "top_level_domain": "",
            },
        },
        id="extraction only path",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "http:"}},
        {
            "url": {
                "domain": "http:",
                "registered_domain": "",
                "subdomain": "",
                "top_level_domain": "",
            }
        },
        id="extraction only schema",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "NOT AN URL"}},
        {
            "url": {
                "domain": "NOT AN URL",
                "registered_domain": "",
                "subdomain": "",
                "top_level_domain": "",
            },
        },
        id="Invalid content (str not url)",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "http://["}},
        {
            "url": {"domain": "http://["},
            "tags": ["invalid_domain_in_url_domain"],
        },
        id="invalid domain",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": ["NOT", "AN", "URL"]}},
        {
            "url": {"domain": ["NOT", "AN", "URL"]},
            "tags": ["invalid_type_in_url_domain"],
        },
        id="invalid content (list)",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": {"NOT": "AN URL"}}},
        {
            "url": {"domain": {"NOT": "AN URL"}},
            "tags": ["invalid_type_in_url_domain"],
        },
        id="invalid content (object)",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": 42}},
        {
            "url": {"domain": 42},
            "tags": ["invalid_type_in_url_domain"],
        },
        id="invalid content (number)",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": False}},
        {
            "url": {
                "domain": False,
            },
            "tags": ["invalid_type_in_url_domain"],
        },
        id="invalid content (boolean)",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": None}},
        {
            "url": {
                "domain": None,
            },
            "tags": ["invalid_type_in_url_domain"],
        },
        id="invalid content (null)",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "www.test.domain.de"}},
        {
            "url": {
                "domain": "www.test.domain.de",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "www.test",
            }
        },
        id="extraction to existing field",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "domain.de"}},
        {
            "url": {
                "domain": "domain.de",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
                "subdomain": "",
            }
        },
        id="extraction without subdomain",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "domain.fubarbo"}},
        {
            "url": {
                "domain": "domain.fubarbo",
                "registered_domain": "",
                "top_level_domain": "",
                "subdomain": "",
            },
        },
        id="extraction without recognized tld",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "http://["}, "tags": ["source"]},
        {
            "url": {
                "domain": "http://[",
            },
            "tags": ["source", "invalid_domain_in_url_domain"],
        },
        id="invalid with existing list in tag field",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "http://["}, "tags": "source"},
        {
            "url": {
                "domain": "http://[",
            },
            "tags": ["source", "invalid_domain_in_url_domain"],
        },
        id="invalid with existing str in tag field",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "domain.co.uk"}},
        {
            "url": {
                "domain": "domain.co.uk",
                "registered_domain": "domain.co.uk",
                "top_level_domain": "co.uk",
                "subdomain": "",
            }
        },
        id="with separated tld",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "123.123.123.123"}},
        {"url": {"domain": "123.123.123.123"}, "tags": ["ip_in_url_domain"]},
        id="with_ipv4_target",
    ),
    pytest.param(
        TEST_RULE,
        {"url": {"domain": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"}},
        {
            "url": {"domain": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"},
            "tags": ["ip_in_url_domain"],
        },
        id="with ipv6 target",
    ),
    pytest.param(
        {
            "filter": "url",
            "domain_label_extractor": {
                "source_fields": ["url.domain"],
                "target_field": "url",
                "overwrite_target": True,
            },
            "description": "",
        },
        {"url": {"domain": "test.domain.de", "subdomain": "exists already"}},
        {
            "url": {
                "domain": "test.domain.de",
                "registered_domain": "domain.de",
                "subdomain": "test",
                "top_level_domain": "de",
            }
        },
        id="overwrites target field",
    ),
    pytest.param(
        {
            "filter": "url",
            "domain_label_extractor": {
                "source_fields": ["url.domain"],
                "target_field": "url",
                "overwrite_target": True,
                "delete_source_fields": True,
            },
            "description": "",
        },
        {"url": {"domain": "test.domain.de", "subdomain": "exists already"}},
        {
            "url": {
                "registered_domain": "domain.de",
                "subdomain": "test",
                "top_level_domain": "de",
            }
        },
        id="delete source fields",
    ),
    pytest.param(
        {
            "filter": "url",
            "domain_label_extractor": {
                "source_fields": ["url.not_existing"],
                "target_field": "url",
                "overwrite_target": True,
                "delete_source_fields": True,
            },
            "description": "",
        },
        {"url": {"domain": "test.domain.de", "subdomain": "exists already"}},
        {
            "url": {"domain": "test.domain.de", "subdomain": "exists already"},
            "tags": ["_domain_label_extractor_missing_field_warning"],
        },
        id="does nothing if source field not exits",
    ),
    pytest.param(
        {
            "filter": "url",
            "domain_label_extractor": {
                "source_fields": ["url.comp\\\\lex\\.domain"],
                "target_field": "url",
            },
            "description": "",
        },
        {
            "url": {"comp\\lex.domain": "http://["},
            "tags": ["url"],
        },
        {
            "url": {"comp\\lex.domain": "http://["},
            "tags": [
                "url",
                "invalid_domain_in_url_comp\\lex.domain",
            ],
        },
        id="invalid domain with escaped dot notation",
    ),
    pytest.param(
        {
            "filter": "source",
            "domain_label_extractor": {
                "source_fields": ["source.comp\\\\lex\\.ip"],
                "target_field": "source",
            },
            "description": "",
        },
        {
            "source": {"comp\\lex.ip": "123.123.123.123"},
            "tags": ["source"],
        },
        {
            "source": {"comp\\lex.ip": "123.123.123.123"},
            "tags": [
                "source",
                "ip_in_source_comp\\lex.ip",
            ],
        },
        id="ip in with escaped dot notation",
    ),
]


multi_rule_test_cases = [
    pytest.param(
        {
            "url": {"domain": "http://["},
            "source": {"domain": "http://["},
            "tags": ["source"],
        },
        {
            "url": {"domain": "http://["},
            "source": {"domain": "http://["},
            "tags": [
                "source",
                "invalid_domain_in_url_domain",
                "invalid_domain_in_source_domain",
            ],
        },
        id="two invalid domains",
    ),
    pytest.param(
        {
            "url": {"domain": "domain.de"},
            "source": {"domain": "http://["},
            "tags": ["source"],
        },
        {
            "url": {
                "domain": "domain.de",
                "registered_domain": "domain.de",
                "subdomain": "",
                "top_level_domain": "de",
            },
            "source": {"domain": "http://["},
            "tags": ["source", "invalid_domain_in_source_domain"],
        },
        id="two domains one is invalid",
    ),
    pytest.param(
        {
            "url": {"domain": "http://["},
            "source": {"domain": "123.123.123.123"},
            "tags": ["source"],
        },
        {
            "url": {"domain": "http://["},
            "source": {"domain": "123.123.123.123"},
            "tags": ["source", "invalid_domain_in_url_domain", "ip_in_source_domain"],
        },
        id="two domains one is invalid one has ip",
    ),
]


class TestDomainLabelExtractor(BaseProcessorTestCase):
    CONFIG = {
        "type": "domain_label_extractor",
        "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @pytest.mark.parametrize(["rule", "document", "expected_output"], test_cases)
    def test_domain_extractor(self, rule, document, expected_output):
        used_document = deepcopy(document)
        self._load_rule(rule)
        self.object.setup()
        self.object.process(used_document)
        assert used_document == expected_output

    @pytest.mark.parametrize(["document", "expected_output"], multi_rule_test_cases)
    def test_domain_extractor_multi_rule(self, document, expected_output):
        used_document = deepcopy(document)

        self.object.process(used_document)
        assert used_document == expected_output

    def test_new_non_default_tagging_field(self):
        config = {
            "Test DomainLabelExtractor Name": {
                "type": "domain_label_extractor",
                "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
                "tagging_field_name": "special_tags",
                "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            }
        }

        domain_label_extractor = Factory.create(configuration=config)
        document = {"url": {"domain": "http://["}}
        expected_output = {
            "url": {"domain": "http://["},
            "special_tags": ["invalid_domain_in_url_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_append_to_non_default_tagging_field(self):
        config = {
            "Test DomainLabelExtractor Name": {
                "type": "domain_label_extractor",
                "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
                "tagging_field_name": "special_tags",
                "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            }
        }

        domain_label_extractor = Factory.create(config)
        document = {"url": {"domain": "http://["}, "special_tags": ["source"]}
        expected_output = {
            "url": {"domain": "http://["},
            "special_tags": ["source", "invalid_domain_in_url_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_domain_extraction_with_existing_output_field(self):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)

    def test_raises_on_invalid_tagging_field(self):
        config = {
            "Test DomainLabelExtractor Name": {
                "type": "domain_label_extractor",
                "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
                "tagging_field_name": "special_tags",
                "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            }
        }

        domain_label_extractor = Factory.create(config)
        domain_label_extractor.setup()
        document = {"url": {"domain": "http://["}, "special_tags": False}
        result = domain_label_extractor.process(document)
        assert len(result.errors) == 1
        assert isinstance(result.errors[0], ProcessingCriticalError)

    def test_raises_field_exists_warning_if_target_field_exits(self):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}
        expected = {
            "tags": ["_domain_label_extractor_failure"],
            "url": {
                "domain": "test.domain.de",
                "subdomain": "exists already",
                "registered_domain": "domain.de",
                "top_level_domain": "de",
            },
        }

        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)
        assert document == expected
