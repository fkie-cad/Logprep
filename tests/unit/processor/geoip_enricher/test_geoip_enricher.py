# pylint: disable=missing-docstring
# pylint: disable=no-self-use
from unittest import mock

import pytest
from geoip2.errors import AddressNotFoundError

from logprep.processor.geoip_enricher.processor import DuplicationError
from tests.unit.processor.base import BaseProcessorTestCase


class ReaderMock(mock.MagicMock):
    def city(self, ip_list):
        if "127.0.0.1" in ip_list:
            raise AddressNotFoundError("127.0.0.1 not found in IP list")
        if "8.8.8.8" in ip_list:

            class MockData:
                longitude = 1.1
                latitude = 2.2
                accuracy_radius = 1337
                name = "myName"
                code = "2342"
                most_specific = mock.MagicMock()

            class City:
                location = MockData()
                continent = MockData()
                country = MockData()
                city = MockData()
                postal = MockData()
                subdivisions = MockData()

            city = City()
            city.continent.name = "MyContinent"
            city.country.name = "MyCountry"
            city.city.name = "MyCity"

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

    def test_geoip_data_added_not_exists(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"client": {"ip": "127.0.0.1"}}

        self.object.process(document)

        assert document.get("geoip") is None

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

    def test_enrich_an_event_geoip_with_existing_differing_geoip(self):
        assert self.object.metrics.number_of_processed_events == 0
        document = {"client": {"ip": "8.8.8.8"}, "geoip": {"test": "test"}}

        with pytest.raises(
            DuplicationError,
            match=r"GeoipEnricher \(Test Instance Name\)\: The following fields "
            r"already existed and were not overwritten by the GeoipEnricher\:"
            r" geoip",
        ):
            self.object.process(document)

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
