from os.path import exists
from logging import getLogger

import pytest

pytest.importorskip('logprep.processor.geoip_enricher')

from logprep.processor.geoip_enricher.factory import GeoIPEnricherFactory
from logprep.processor.geoip_enricher.processor import DuplicationError

logger = getLogger()
geoip_db_path = 'tests/testdata/external/GeoLite2-City.mmdb'
rules_dir = 'tests/testdata/unit/geoip_enricher/rules'


@pytest.fixture()
def geoip_enricher():
    config = {
        'type': 'geoip_enricher',
        'rules': [rules_dir],
        'db_path': geoip_db_path,
        'tree_config': 'tests/testdata/unit/shared_data/tree_config.json'
    }

    geoip_enricher = GeoIPEnricherFactory.create('test-geoip-enricher', config, logger)
    return geoip_enricher


@pytest.mark.skipif(not exists(geoip_db_path), reason='GeoIP db required.')
class TestGeoIPEnricher:
    def test_geoip_data_added(self, geoip_enricher):
        assert geoip_enricher.events_processed_count() == 0
        document = {'client': {'ip': '1.2.3.4'}}

        geoip_enricher.process(document)

    def test_geoip_data_added_not_exists(self, geoip_enricher):
        assert geoip_enricher.events_processed_count() == 0
        document = {'client': {'ip': '127.0.0.1'}}

        geoip_enricher.process(document)

        assert document.get('geoip') is None

    def test_nothing_to_enrich(self, geoip_enricher):
        assert geoip_enricher.events_processed_count() == 0
        document = {'something': {'something': '1.2.3.4'}}

        geoip_enricher.process(document)
        assert 'geoip' not in document.keys()

    def test_geoip_data_added_not_valid(self, geoip_enricher):
        assert geoip_enricher.events_processed_count() == 0
        document = {'client': {'ip': '333.333.333.333'}}

        geoip_enricher.process(document)

        assert document.get('geoip') is None

    def test_enrich_an_event_geoip(self, geoip_enricher):
        assert geoip_enricher.events_processed_count() == 0
        document = {'client': {'ip': '8.8.8.8'}}

        geoip_enricher.process(document)

        geoip = document.get('geoip')
        assert isinstance(geoip, dict)
        assert geoip.get('type') == 'Feature'
        assert isinstance(geoip.get('geometry'), dict)
        assert geoip['geometry'].get('type') == 'Point'
        assert isinstance(geoip['geometry'].get('coordinates'), list)
        assert isinstance(geoip['geometry']['coordinates'][0], float)
        assert isinstance(geoip['geometry']['coordinates'][1], float)
        assert isinstance(geoip.get('properties'), dict)
        assert isinstance(geoip['properties'].get('continent'), str)
        assert isinstance(geoip['properties'].get('country'), str)
        assert isinstance(geoip['properties'].get('accuracy_radius'), int)

    def test_enrich_an_event_geoip_with_existing_differing_geoip(self, geoip_enricher):
        assert geoip_enricher.events_processed_count() == 0
        document = {'client': {'ip': '8.8.8.8'}, 'geoip': {'test': 'test'}}

        with pytest.raises(DuplicationError, match=r'GeoIPEnricher \(test-geoip-enricher\)\: The following fields '
                                                   r'already existed and were not overwritten by the GeoIPEnricher\:'
                                                   r' geoip'):
            geoip_enricher.process(document)

    def test_configured_dotted_output_field(self, geoip_enricher):
        assert geoip_enricher.events_processed_count() == 0
        document = {'source': {'ip': '8.8.8.8'}}

        geoip_enricher.process(document)
        assert document.get('source', {}).get('geo', {}).get('ip') is not None
