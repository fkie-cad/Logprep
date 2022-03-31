# pylint: disable=missing-docstring
from os.path import exists
from logging import getLogger

import pytest
from unittest import mock
from geoip2.errors import AddressNotFoundError
from tests.unit.processor.base import BaseProcessorTestCase

pytest.importorskip("logprep.processor.geoip_enricher")

from logprep.processor.geoip_enricher.factory import GeoIPEnricherFactory
from logprep.processor.geoip_enricher.processor import DuplicationError

logger = getLogger()
rules_dir = "tests/testdata/unit/geoip_enricher/rules"


class ReaderMock(mock.MagicMock):
    def city(self, ip):
        if "127.0.0.1" in ip:
            raise AddressNotFoundError
        if "8.8.8.8" in ip:

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


class TestGeoIPEnricher(BaseProcessorTestCase):

    mocks = {"geoip2.database.Reader": {"new": ReaderMock()}}

    factory = GeoIPEnricherFactory

    CONFIG = {
        "type": "geoip_enricher",
        "specific_rules": ["tests/testdata/unit/geoip_enricher/rules/specific"],
        "generic_rules": ["tests/testdata/unit/geoip_enricher/rules/generic"],
        "db_path": "tests/testdata/external/GeoLite2-City.mmdb",
        "tree_config": "tests/testdata/unit/shared_data/tree_config.json",
    }

    @property
    def generic_rules_dirs(self):
        return self.CONFIG["generic_rules"]

    @property
    def specific_rules_dirs(self):
        return self.CONFIG["specific_rules"]

    def test_geoip_data_added(self, geoip_enricher):
        assert geoip_enricher.ps.processed_count == 0
        document = {"client": {"ip": "1.2.3.4"}}

        geoip_enricher.process(document)

    def test_geoip_data_added_not_exists(self, geoip_enricher):
        assert geoip_enricher.ps.processed_count == 0
        document = {"client": {"ip": "127.0.0.1"}}

        geoip_enricher.process(document)

        assert document.get("geoip") is None

    def test_nothing_to_enrich(self, geoip_enricher):
        assert geoip_enricher.ps.processed_count == 0
        document = {"something": {"something": "1.2.3.4"}}

        geoip_enricher.process(document)
        assert "geoip" not in document.keys()

    def test_geoip_data_added_not_valid(self, geoip_enricher):
        assert geoip_enricher.ps.processed_count == 0
        document = {"client": {"ip": "333.333.333.333"}}

        geoip_enricher.process(document)

        assert document.get("geoip") is None

    def test_enrich_an_event_geoip(self, geoip_enricher):
        assert geoip_enricher.ps.processed_count == 0
        document = {"client": {"ip": "8.8.8.8"}}

        geoip_enricher.process(document)

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

    def test_enrich_an_event_geoip_with_existing_differing_geoip(self, geoip_enricher):
        assert geoip_enricher.ps.processed_count == 0
        document = {"client": {"ip": "8.8.8.8"}, "geoip": {"test": "test"}}

        with pytest.raises(
            DuplicationError,
            match=r"GeoIPEnricher \(test-geoip-enricher\)\: The following fields "
            r"already existed and were not overwritten by the GeoIPEnricher\:"
            r" geoip",
        ):
            geoip_enricher.process(document)

    def test_configured_dotted_output_field(self, geoip_enricher):
        assert geoip_enricher.ps.processed_count == 0
        document = {"source": {"ip": "8.8.8.8"}}

        geoip_enricher.process(document)
        assert document.get("source", {}).get("geo", {}).get("ip") is not None
