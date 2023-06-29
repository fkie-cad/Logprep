# pylint: disable=protected-access
# pylint: disable=missing-docstring

import hashlib
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path

import responses

from logprep.factory import Factory
from logprep.processor.base.exceptions import ProcessingWarning
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
        }
        expected_tags = [
            "source",
            "invalid_domain_in_url_domain",
            "invalid_domain_in_source_domain",
        ]

        self.object.process(document)
        tags = document.pop("tags")

        assert document == expected_output
        assert set(tags) == set(expected_tags)

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
        }
        expected_tags = ["source", "invalid_domain_in_url_domain", "ip_in_source_domain"]
        self.object.process(document)
        tags = document.pop("tags")

        assert document == expected_output
        assert set(tags) == set(expected_tags)

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

        domain_label_extractor = Factory.create(configuration=config, logger=self.logger)
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

        domain_label_extractor = Factory.create(config, self.logger)
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

    def test_domain_extraction_with_existing_output_field(self, caplog):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}

        with caplog.at_level(logging.WARNING):
            self.object.process(document)
        assert re.match(".*FieldExistsWarning.*", caplog.text)

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
        self._load_specific_rule(rule_dict)
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
        self._load_specific_rule(rule_dict)
        self.object.process(document)
        assert document == expected

    def test_does_nothing_if_source_field_not_exits(self):
        document = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}
        expected = {"url": {"domain": "test.domain.de", "subdomain": "exists already"}}
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
        self._load_specific_rule(rule_dict)
        self.object.process(document)
        assert document == expected

    def test_raises_duplication_error_if_target_field_exits(self, caplog):
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

        rule_dict = {
            "filter": "url",
            "domain_label_extractor": {
                "source_fields": ["url.domain"],
                "target_field": "url",
            },
            "description": "",
        }
        self._load_specific_rule(rule_dict)
        with caplog.at_level(logging.WARNING):
            self.object.process(document)
        assert re.match(".*FieldExistsWarning.*", caplog.text)
        assert document == expected

    @responses.activate
    def test_setup_downloads_tld_lists_to_separate_process_file(self):
        tld_list = "http://db-path-target/list.dat"
        tld_list_path = Path("/usr/bin/ls") if Path("/usr/bin/ls").exists() else Path("/bin/ls")
        tld_list_content = tld_list_path.read_bytes()
        expected_checksum = hashlib.md5(tld_list_content).hexdigest()  # nosemgrep
        responses.add(responses.GET, tld_list, tld_list_content)
        self.object._config.tld_lists = [tld_list]
        self.object.setup()
        logprep_tmp_dir = Path(tempfile.gettempdir()) / "logprep"
        downloaded_file = logprep_tmp_dir / f"{self.object.name}-tldlist-0.dat"
        assert downloaded_file.exists()
        downloaded_checksum = hashlib.md5(downloaded_file.read_bytes()).hexdigest()  # nosemgrep
        assert expected_checksum == downloaded_checksum
        # delete testfile
        shutil.rmtree(logprep_tmp_dir)

    @responses.activate
    def test_setup_doesnt_overwrite_already_existing_tld_list_file(self):
        tld_list = "http://db-path-target/list.dat"
        tld_list_content = "some content"
        responses.add(responses.GET, tld_list, tld_list_content.encode("utf8"))

        logprep_tmp_dir = Path(tempfile.gettempdir()) / "logprep"
        os.makedirs(logprep_tmp_dir, exist_ok=True)
        tld_temp_file = logprep_tmp_dir / f"{self.object.name}-tldlist-0.dat"

        pre_existing_content = "file exists already"
        tld_temp_file.touch()
        tld_temp_file.write_bytes(pre_existing_content.encode("utf8"))
        self.object._config.tld_lists = [tld_list]
        self.object.setup()
        assert tld_temp_file.exists()
        assert tld_temp_file.read_bytes().decode("utf8") == pre_existing_content
        assert tld_temp_file.read_bytes().decode("utf8") != tld_list_content
        shutil.rmtree(logprep_tmp_dir)  # delete testfile
