# pylint: disable=protected-access
# pylint: disable=missing-docstring


from copy import deepcopy

import pytest

from logprep.factory import Factory
from logprep.processor.base.exceptions import FieldExistsWarning
from tests.unit.processor.base import BaseProcessorTestCase


class TestDomainLabelExtractor(BaseProcessorTestCase):
    CONFIG = {
        "type": "domain_label_extractor",
        "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    test_cases = [
        pytest.param(
            {"url": {"domain": "https://url.full.domain.de/path/file?param=1"}},
            {
                "url": {
                    "domain": "https://url.full.domain.de/path/file?param=1",
                    "registered_domain": "domain.de",
                    "top_level_domain": "de",
                    "subdomain": "url.full",
                }
            },
            id="extraction_from_full_url",
        ),
        pytest.param(
            {"url": {"domain": "https://url.full.domain.de/path/file?param=1"}},
            {
                "url": {
                    "domain": "https://url.full.domain.de/path/file?param=1",
                    "registered_domain": "domain.de",
                    "top_level_domain": "de",
                    "subdomain": "url.full",
                }
            },
            id="extraction_from_full_url",
        ),
        pytest.param(
            {"url": {"domain": "/path/file?param=1"}},
            {
                "url": {
                    "domain": "/path/file?param=1",
                },
                "tags": ["invalid_domain_in_url_domain"],
            },
            id="extraction_only_path",
        ),
        pytest.param(
            {"url": {"domain": "http:"}},
            {
                "url": {
                    "domain": "http:",
                },
                "tags": ["invalid_url_domain_in_url_domain"],
            },
            id="extraction_only_schema",
        ),
        pytest.param(
            {"url": {"domain": "NOT AN URL"}},
            {
                "url": {"domain": "NOT AN URL"},
                "tags": ["invalid_type_in_url_domain"],
            },
            id="Invalid content (str not url)",
        ),
        pytest.param(
            {"url": {"domain": ["NOT", "AN", "URL"]}},
            {
                "url": {"domain": ["NOT", "AN", "URL"]},
                "tags": ["invalid_type_in_url_domain"],
            },
            id="Invalid content (list)",
        ),
        pytest.param(
            {"url": {"domain": {"NOT": "AN URL"}}},
            {
                "url": {"domain": {"NOT": "AN URL"}},
                "tags": ["invalid_type_in_url_domain"],
            },
            id="Invalid content (object)",
        ),
        pytest.param(
            {"url": {"domain": 42}},
            {
                "url": {"domain": 42},
                "tags": ["invalid_type_in_url_domain"],
            },
            id="Invalid content (number)",
        ),
        pytest.param(
            {"url": {"domain": False}},
            {
                "url": {
                    "domain": False,
                },
                "tags": ["invalid_type_in_url_domain"],
            },
            id="Invalid content (boolean)",
        ),
        pytest.param(
            {"url": {"domain": None}},
            {
                "url": {
                    "domain": None,
                },
                "tags": ["invalid_type_in_url_domain"],
            },
            id="Invalid content (null)",
        ),
        pytest.param(
            {"url": {"domain": "www.test.domain.de"}},
            {
                "url": {
                    "domain": "www.test.domain.de",
                    "registered_domain": "domain.de",
                    "top_level_domain": "de",
                    "subdomain": "www.test",
                }
            },
            id="extraction_to_existing_field",
        ),
        pytest.param(
            {"url": {"domain": "www.test.domain.de"}},
            {
                "url": {
                    "domain": "www.test.domain.de",
                    "registered_domain": "domain.de",
                    "top_level_domain": "de",
                    "subdomain": "www.test",
                }
            },
            id="extraction_to_existing_field",
        ),
        pytest.param(
            {"url": {"domain": "domain.de"}},
            {
                "url": {
                    "domain": "domain.de",
                    "registered_domain": "domain.de",
                    "top_level_domain": "de",
                    "subdomain": "",
                }
            },
            id="extraction_without_subdomain",
        ),
        pytest.param(
            {"url": {"domain": "domain.fubarbo"}},
            {
                "url": {"domain": "domain.fubarbo"},
                "tags": ["invalid_domain_in_url_domain"],
            },
            id="extraction_without_recognized_tld",
        ),
        pytest.param(
            {"url": {"domain": "domain.fubarbo"}, "tags": ["source"]},
            {
                "url": {"domain": "domain.fubarbo"},
                "tags": ["source", "invalid_domain_in_url_domain"],
            },
            id="without_recognized_tld_with_existing_tag_field",
        ),
        pytest.param(
            {
                "url": {"domain": "domain.fubarbo"},
                "source": {"domain": "domain.invalid"},
                "tags": ["source"],
            },
            {
                "url": {"domain": "domain.fubarbo"},
                "source": {"domain": "domain.invalid"},
                "tags": [
                    "source",
                    "invalid_domain_in_url_domain",
                    "invalid_domain_in_source_domain",
                ],
            },
            id="two_invalid_domains",
        ),
        pytest.param(
            {
                "url": {"domain": "domain.de"},
                "source": {"domain": "domain.invalid"},
                "tags": ["source"],
            },
            {
                "url": {
                    "domain": "domain.de",
                    "registered_domain": "domain.de",
                    "subdomain": "",
                    "top_level_domain": "de",
                },
                "source": {"domain": "domain.invalid"},
                "tags": ["source", "invalid_domain_in_source_domain"],
            },
            id="two_domains_one_is_invalid",
        ),
        pytest.param(
            {
                "url": {"domain": "domain.fubarbo"},
                "source": {"domain": "123.123.123.123"},
                "tags": ["source"],
            },
            {
                "url": {"domain": "domain.fubarbo"},
                "source": {"domain": "123.123.123.123"},
                "tags": ["source", "invalid_domain_in_url_domain", "ip_in_source_domain"],
            },
            id="two_domains_one_is_invalid_one_has_ip",
        ),
        pytest.param(
            {"url": {"domain": "domain.co.uk"}},
            {
                "url": {
                    "domain": "domain.co.uk",
                    "registered_domain": "domain.co.uk",
                    "top_level_domain": "co.uk",
                    "subdomain": "",
                }
            },
            id="with_separated_tld",
        ),
        pytest.param(
            {"url": {"domain": "123.123.123.123"}},
            {"url": {"domain": "123.123.123.123"}, "tags": ["ip_in_url_domain"]},
            id="with_ipv4_target",
        ),
        pytest.param(
            {"url": {"domain": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"}},
            {
                "url": {"domain": "2001:0db8:85a3:0000:0000:8a2e:0370:7334"},
                "tags": ["ip_in_url_domain"],
            },
            id="with_ipv6_target",
        ),
    ]

    @pytest.mark.parametrize(["document", "expected_output"], test_cases)
    def test_domain_extractor(self, document, expected_output):
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
                "rules": ["tests/testdata/unit/domain_label_extractor/rules"],
                "tagging_field_name": "special_tags",
                "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
            }
        }

        domain_label_extractor = Factory.create(config)
        document = {"url": {"domain": "domain.fubarbo"}, "special_tags": ["source"]}
        expected_output = {
            "url": {"domain": "domain.fubarbo"},
            "special_tags": ["source", "invalid_domain_in_url_domain"],
        }

        domain_label_extractor.process(document)
        assert document == expected_output

    def test_domain_extraction_with_existing_output_field(self):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}
        result = self.object.process(document)
        assert len(result.warnings) == 1
        assert isinstance(result.warnings[0], FieldExistsWarning)

    def test_domain_extraction_overwrites_target_field(self):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}
        expected = {
            "url": {
                "domain": "test.domain.de",
                "registered_domain": "domain.de",
                "subdomain": "test",
                "top_level_domain": "de",
            }
        }
        rule_dict = {
            "filter": "url",
            "domain_label_extractor": {
                "source_fields": ["url.domain"],
                "target_field": "url",
                "overwrite_target": True,
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.process(document)
        assert document == expected

    def test_domain_extraction_delete_source_fields(self):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}
        expected = {
            "url": {
                "registered_domain": "domain.de",
                "subdomain": "test",
                "top_level_domain": "de",
            }
        }
        rule_dict = {
            "filter": "url",
            "domain_label_extractor": {
                "source_fields": ["url.domain"],
                "target_field": "url",
                "overwrite_target": True,
                "delete_source_fields": True,
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.process(document)
        assert document == expected

    def test_does_nothing_if_source_field_not_exits(self):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}
        expected = {
            "url": {"domain": "test.domain.de", "subdomain": "exists already"},
            "tags": ["_domain_label_extractor_missing_field_warning"],
        }
        rule_dict = {
            "filter": "url",
            "domain_label_extractor": {
                "source_fields": ["url.not_existing"],
                "target_field": "url",
                "overwrite_target": True,
                "delete_source_fields": True,
            },
            "description": "",
        }
        self._load_rule(rule_dict)
        self.object.process(document)
        assert document == expected

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

    def test_invalid_domain_with_escaped_dot_notation(self):
        document = {
            "url": {"comp\\lex.domain": "domain.fubarbo"},
            "tags": ["url"],
        }
        expected_output = {
            "url": {"comp\\lex.domain": "domain.fubarbo"},
        }
        expected_tags = [
            "url",
            "invalid_domain_in_url_comp\\lex.domain",
        ]

        rule_dict = {
            "filter": "url",
            "domain_label_extractor": {
                "source_fields": ["url.comp\\\\lex\\.domain"],
                "target_field": "url",
            },
            "description": "",
        }
        self._load_rule(rule_dict)

        self.object.process(document)
        tags = document.pop("tags")

        assert document == expected_output
        assert set(tags) == set(expected_tags)

    def test_ip_in_with_escaped_dot_notation(self):
        document = {
            "source": {"comp\\lex.ip": "123.123.123.123"},
            "tags": ["source"],
        }
        expected_output = {
            "source": {"comp\\lex.ip": "123.123.123.123"},
        }
        expected_tags = [
            "source",
            "ip_in_source_comp\\lex.ip",
        ]

        rule_dict = {
            "filter": "source",
            "domain_label_extractor": {
                "source_fields": ["source.comp\\\\lex\\.ip"],
                "target_field": "source",
            },
            "description": "",
        }
        self._load_rule(rule_dict)

        self.object.process(document)
        tags = document.pop("tags")

        assert document == expected_output
        assert set(tags) == set(expected_tags)
