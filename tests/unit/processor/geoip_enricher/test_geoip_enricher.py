# pylint: disable=missing-docstring
# pylint: disable=no-member
# pylint: disable=protected-access
# pylint: disable=too-many-statements
import hashlib
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import responses
from geoip2.errors import AddressNotFoundError

from logprep.processor.base.exceptions import ProcessingWarning
from tests.unit.processor.base import BaseProcessorTestCase


class ReaderMock(mock.MagicMock):
    def city(self, ip_list):
        class City:
            location = mock.MagicMock()
            continent = mock.MagicMock()
            country = mock.MagicMock()
            city = mock.MagicMock()
            postal = mock.MagicMock()
            subdivisions = mock.MagicMock()

        if "127.0.0.1" in ip_list:
            raise AddressNotFoundError("127.0.0.1 not found in IP list")
        if "8.8.8.8" in ip_list:
            city = City()
            city.location.accuracy_radius = 1337
            city.location.longitude = 1.1
            city.location.latitude = 2.2
            city.location.time_zone = "Europe/Berlin"
            city.continent.name = "MyContinent"
            city.continent.code = "MCT"
            city.country.name = "MyCountry"
            city.country.iso_code = "MCR"
            city.city.name = "MyCity"
            city.postal.code = "2342"
            city.subdivisions.most_specific = mock.MagicMock()
            city.subdivisions.most_specific.name = "MySubdivision"
            return city
        if "13.21.21.37" in ip_list:
            city = City()
            city.location.accuracy_radius = 1337
            city.location.longitude = 1.1
            city.location.latitude = 2.2
            city.location.time_zone = None
            city.continent.name = None
            city.continent.code = None
            city.country.name = None
            city.country.iso_code = None
            city.city.name = None
            city.postal.code = None
            city.subdivisions.most_specific = mock.MagicMock()
            city.subdivisions.most_specific.name = None
            return city
        if any(ip in ip_list for ip in ["55.55.55.51", "55.55.55.52", "55.55.55.53"]):
            city = City()
            city.location.accuracy_radius = 1337
            city.location.time_zone = None
            city.continent.name = None
            city.continent.code = None
            city.country.name = None
            city.country.iso_code = None
            city.city.name = None
            city.postal.code = None
            city.subdivisions.most_specific = mock.MagicMock()
            city.subdivisions.most_specific.name = None
            city.location.longitude = None
            city.location.latitude = None
            if "55.55.55.52" in ip_list:
                city.location.latitude = 1.1
            if "55.55.55.53" in ip_list:
                city.location.longitude = 2.2
            return city
        return mock.MagicMock()


class TestGeoipEnricher(BaseProcessorTestCase):
    mocks = {"geoip2.database.Reader": {"new": ReaderMock()}}

    CONFIG = {
        "type": "geoip_enricher",
        "specific_rules": ["tests/testdata/unit/geoip_enricher/rules/specific"],
        "generic_rules": ["tests/testdata/unit/geoip_enricher/rules/generic"],
        "db_path": "tests/testdata/mock_external/MockGeoLite2-City.mmdb",
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @property
    def generic_rules_dirs(self):
        return self.CONFIG["generic_rules"]

    @property
    def specific_rules_dirs(self):
        return self.CONFIG["specific_rules"]

    def test_geoip_data_added(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"client": {"ip": "1.2.3.4"}}

        self.object.process(document)

        assert document.get("geoip")

    def test_geoip_data_added_not_exists(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"client": {"ip": "127.0.0.1"}}

        self.object.process(document)

        assert document.get("geoip") is None

    def test_no_geoip_data_added_if_source_field_is_none(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"client": {"ip": None}}

        self.object.process(document)

        assert document.get("geoip") is None

    def test_source_field_is_none_raises_processing_warning(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"client": {"ip": None}}

        with pytest.raises(
            ProcessingWarning,
            match=re.escape("Value of IP field 'client.ip' is 'None'"),
        ):
            self.object._apply_rules(document, self.object.rules[0])

    def test_nothing_to_enrich(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"something": {"something": "1.2.3.4"}}

        self.object.process(document)
        assert "geoip" not in document

    def test_geoip_data_added_not_valid(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"client": {"ip": "333.333.333.333"}}

        self.object.process(document)

        assert document.get("geoip") is None

    def test_enrich_an_event_geoip(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"client": {"ip": "8.8.8.8"}}

        self.object.process(document)

        geoip = document.get("geoip")
        assert isinstance(geoip, dict)
        assert geoip.get("type") == "Feature"
        assert isinstance(geoip.get("geometry"), dict)
        assert geoip["geometry"].get("type") == "Point"
        assert isinstance(geoip["geometry"].get("coordinates"), list)
        assert geoip["geometry"]["coordinates"][0] == 1.1
        assert geoip["geometry"]["coordinates"][1] == 2.2
        assert isinstance(geoip.get("properties"), dict)
        assert geoip["properties"].get("continent") == "MyContinent"
        assert geoip["properties"].get("country") == "MyCountry"
        assert geoip["properties"].get("accuracy_radius") == 1337

    def test_enrich_an_event_geoip_with_existing_differing_geoip(self, caplog):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"client": {"ip": "8.8.8.8"}, "geoip": {"type": "Feature"}}

        with caplog.at_level(logging.WARNING):
            self.object.process(document)
        assert re.match(".*FieldExistsWarning.*geoip.type", caplog.text)

    def test_configured_dotted_output_field(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"source": {"ip": "8.8.8.8"}}

        self.object.process(document)
        assert document.get("source", {}).get("geo", {}).get("ip") is not None

    def test_delete_source_field(self):
        document = {
            "client": {"ip": "8.8.8.8", "other_key": "I am here to keep client field alive"}
        }
        rule_dict = {
            "filter": "client",
            "geoip_enricher": {
                "source_fields": ["client.ip"],
                "target_field": "source.geo.ip",
                "delete_source_fields": True,
            },
            "description": "",
        }
        self._load_specific_rule(rule_dict)
        self.object.process(document)
        assert "client" in document
        assert "ip" not in document.get("client")

    def test_overwrite_target_field(self):
        document = {"client": {"ip": "8.8.8.8"}}
        rule_dict = {
            "filter": "client",
            "geoip_enricher": {
                "source_fields": ["client.ip"],
                "target_field": "client.ip",
                "overwrite_target": True,
            },
            "description": "",
        }
        self._load_specific_rule(rule_dict)
        self.object.process(document)
        assert "client" in document
        assert document.get("client").get("ip").get("type") is not None

    def test_specify_all_target_sub_fields(self):
        document = {"client": {"ip": "8.8.8.8"}}
        rule_dict = {
            "filter": "client",
            "geoip_enricher": {
                "source_fields": ["client.ip"],
                "target_field": "client.default_output",
                "customize_target_subfields": {
                    "type": "client.custom_output.type",
                    "geometry.type": "client.custom_output.geometry_type",
                    "geometry.coordinates": "client.custom_output.location",
                    "properties.accuracy_radius": "client.custom_output.accuracy",
                    "properties.continent": "client.custom_output.continent_name",
                    "properties.continent_code": "client.custom_output.continent_code",
                    "properties.country": "client.custom_output.country_name",
                    "properties.city": "client.custom_output.city_name",
                    "properties.postal_code": "client.custom_output.postal_code",
                    "properties.subdivision": "client.custom_output.subdivision",
                    "properties.time_zone": "client.custom_output.timezone",
                    "properties.country_iso_code": "client.custom_output.country_iso_code",
                },
            },
            "description": "",
        }
        self._load_specific_rule(rule_dict)
        self.object.process(document)
        expected_event = {
            "client": {
                "custom_output": {
                    "type": "Feature",
                    "geometry_type": "Point",
                    "location": [1.1, 2.2],
                    "accuracy": 1337,
                    "continent_name": "MyContinent",
                    "country_name": "MyCountry",
                    "city_name": "MyCity",
                    "postal_code": "2342",
                    "subdivision": "MySubdivision",
                    "continent_code": "MCT",
                    "country_iso_code": "MCR",
                    "timezone": "Europe/Berlin",
                },
                "ip": "8.8.8.8",
            }
        }
        assert document == expected_event
        assert document.get("client", {}).get("default_output") is None

    def test_specify_some_target_sub_fields(self):
        document = {"client": {"ip": "8.8.8.8"}}
        rule_dict = {
            "filter": "client",
            "geoip_enricher": {
                "source_fields": ["client.ip"],
                "target_field": "client.default_output",
                "customize_target_subfields": {
                    "geometry.coordinates": "client.custom_output.location",
                    "properties.accuracy_radius": "client.custom_output.accuracy",
                    "properties.continent": "client.custom_output.continent_name",
                    "properties.continent_code": "client.custom_output.continent_code",
                },
            },
            "description": "",
        }
        self._load_specific_rule(rule_dict)
        self.object.process(document)
        expected_event = {
            "client": {
                "custom_output": {
                    "accuracy": 1337,
                    "continent_code": "MCT",
                    "continent_name": "MyContinent",
                    "location": [1.1, 2.2],
                },
                "default_output": {
                    "geometry": {"type": "Point"},
                    "properties": {
                        "city": "MyCity",
                        "country": "MyCountry",
                        "country_iso_code": "MCR",
                        "postal_code": "2342",
                        "subdivision": "MySubdivision",
                        "time_zone": "Europe/Berlin",
                    },
                    "type": "Feature",
                },
                "ip": "8.8.8.8",
            }
        }
        assert document == expected_event

    def test_specify_unknown_target_sub_fields(self):
        rule_dict = {
            "filter": "client",
            "geoip_enricher": {
                "source_fields": ["client.ip"],
                "target_field": "client.default_output",
                "customize_target_subfields": {
                    "unknown.default.field": "some.location",
                },
            },
            "description": "",
        }
        with pytest.raises(ValueError, match=r"\'customize_target_subfields\' must be in"):
            self._load_specific_rule(rule_dict)

    def test_geoip_db_returns_only_limited_data_without_missing_coordinates(self):
        document = {"client": {"ip": "13.21.21.37"}}
        rule_dict = {
            "filter": "client",
            "geoip_enricher": {
                "source_fields": ["client.ip"],
            },
            "description": "",
        }
        self._load_specific_rule(rule_dict)
        self.object.process(document)
        expected_event = {
            "client": {"ip": "13.21.21.37"},
            "geoip": {
                "geometry": {"coordinates": [1.1, 2.2], "type": "Point"},
                "properties": {"accuracy_radius": 1337},
                "type": "Feature",
            },
        }
        assert document == expected_event

    @pytest.mark.parametrize(
        "source_ip",
        ["55.55.55.51", "55.55.55.52", "55.55.55.53"],
    )
    def test_geoip_db_returns_only_limited_data_with_missing_coordinates(self, source_ip):
        document = {"client": {"ip": source_ip}}
        rule_dict = {
            "filter": "client",
            "geoip_enricher": {
                "source_fields": ["client.ip"],
            },
            "description": "",
        }
        self._load_specific_rule(rule_dict)
        self.object.process(document)
        expected_event = {
            "client": {"ip": source_ip},
            "geoip": {
                "properties": {"accuracy_radius": 1337},
                "type": "Feature",
            },
        }
        assert document == expected_event

    @responses.activate
    def test_setup_downloads_geoip_database_if_not_exits(self):
        geoip_database_path = "http://db-path-target/db_file.mmdb"
        db_path = Path("/usr/bin/ls") if Path("/usr/bin/ls").exists() else Path("/bin/ls")
        db_path_content = db_path.read_bytes()
        expected_checksum = hashlib.md5(db_path_content).hexdigest()  # nosemgrep
        responses.add(responses.GET, geoip_database_path, db_path_content)
        self.object._config.db_path = geoip_database_path
        self.object.setup()
        logprep_tmp_dir = Path(tempfile.gettempdir()) / "logprep"
        downloaded_file = logprep_tmp_dir / f"{self.object.name}.mmdb"
        assert downloaded_file.exists()
        downloaded_checksum = hashlib.md5(downloaded_file.read_bytes()).hexdigest()  # nosemgrep
        assert expected_checksum == downloaded_checksum
        # delete testfile
        shutil.rmtree(logprep_tmp_dir)

    @responses.activate
    def test_setup_doesnt_overwrite_already_existing_geomap_file(self):
        tld_list = "http://db-path-target/db_file.mmdb"
        tld_list_content = "some content"
        responses.add(responses.GET, tld_list, tld_list_content.encode("utf8"))

        logprep_tmp_dir = Path(tempfile.gettempdir()) / "logprep"
        os.makedirs(logprep_tmp_dir, exist_ok=True)
        tld_temp_file = logprep_tmp_dir / f"{self.object.name}.mmdb"

        pre_existing_content = "file exists already"
        tld_temp_file.touch()
        tld_temp_file.write_bytes(pre_existing_content.encode("utf8"))
        self.object._config.tld_lists = [tld_list]
        self.object.setup()
        assert tld_temp_file.exists()
        assert tld_temp_file.read_bytes().decode("utf8") == pre_existing_content
        assert tld_temp_file.read_bytes().decode("utf8") != tld_list_content
        shutil.rmtree(logprep_tmp_dir)  # delete testfile
