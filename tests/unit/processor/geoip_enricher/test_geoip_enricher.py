# pylint: disable=missing-docstring
# pylint: disable=no-member
from unittest import mock

import pytest
from geoip2.errors import AddressNotFoundError

from logprep.processor.base.exceptions import DuplicationError
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
        document = {"client": {"ip": "8.8.8.8"}, "geoip": {"type": "Feature"}}

        with pytest.raises(
            DuplicationError,
            match=r"The following fields could not be written, because one or more subfields "
            r"existed and could not be extended: geoip.type",
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

    def test_geoip_db_returns_only_limited_data(self):
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
