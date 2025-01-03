"""
GeoipEnricher
=============

Processor to enrich log messages with geolocalization information

Processor Configuration
^^^^^^^^^^^^^^^^^^^^^^^
..  code-block:: yaml
    :linenos:

    - geoipenrichername:
        type: geoip_enricher
        rules:
            - tests/testdata/geoip_enricher/rules
        db_path: /path/to/GeoLite2-City.mmdb

.. autoclass:: logprep.processor.geoip_enricher.processor.GeoipEnricher.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

.. automodule:: logprep.processor.geoip_enricher.rule
"""

import logging
import os
import tempfile
from functools import cached_property
from ipaddress import ip_address
from pathlib import Path

from attr import define, field, validators
from filelock import FileLock
from geoip2 import database
from geoip2.errors import AddressNotFoundError

from logprep.processor.field_manager.processor import FieldManager
from logprep.processor.geoip_enricher.rule import GEOIP_DATA_STUBS, GeoipEnricherRule
from logprep.util.getter import GetterFactory
from logprep.util.helper import add_fields_to, get_dotted_field_value

logger = logging.getLogger("GeoipEnricher")


class GeoipEnricher(FieldManager):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(FieldManager.Config):
        """geoip_enricher config"""

        db_path: str = field(validator=validators.instance_of(str))
        """Path to a `Geo2Lite` city database by `Maxmind` in binary format.
            This must be provided separately.
            The file will be downloaded or copied and cached.
            For valid URI formats see :ref:`getters`
            This product includes GeoLite2 data created by MaxMind, available from
            https://www.maxmind.com."""

    __slots__ = []

    rule_class = GeoipEnricherRule

    @cached_property
    def _city_db(self):
        db_path = Path(self._config.db_path)
        if not db_path.exists():
            logger.debug("start geoip database download...")
            logprep_tmp_dir = Path(tempfile.gettempdir()) / "logprep"
            os.makedirs(logprep_tmp_dir, exist_ok=True)
            db_path_file = logprep_tmp_dir / f"{self.name}.mmdb"
            if not os.path.isfile(db_path_file):
                with FileLock(db_path_file):
                    db_path_file.touch()
                    db_path_file.write_bytes(
                        GetterFactory.from_string(str(self._config.db_path)).get_raw()
                    )
            db_path = str(db_path_file.absolute())
            logger.debug("finished geoip database download.")
        return database.Reader(db_path)

    def setup(self):
        super().setup()
        _ = self._city_db  # trigger download

    def _try_getting_geoip_data(self, ip_string):
        try:
            ip_addr = str(ip_address(ip_string))
            ip_data = self._city_db.city(ip_addr)

            geoip_data = GEOIP_DATA_STUBS.copy()

            geoip_data |= {
                "properties.accuracy_radius": ip_data.location.accuracy_radius,
                "properties.continent": ip_data.continent.name,
                "properties.continent_code": ip_data.continent.code,
                "properties.country": ip_data.country.name,
                "properties.country_iso_code": ip_data.country.iso_code,
                "properties.time_zone": ip_data.location.time_zone,
                "properties.city": ip_data.city.name,
                "properties.postal_code": ip_data.postal.code,
                "properties.subdivision": ip_data.subdivisions.most_specific.name,
            }

            if ip_data.location.longitude and ip_data.location.latitude:
                geoip_data.update(
                    {
                        "geometry.type": "Point",
                        "geometry.coordinates": [
                            ip_data.location.longitude,
                            ip_data.location.latitude,
                        ],
                    }
                )

            return geoip_data
        except (ValueError, AddressNotFoundError):
            return {}

    def _apply_rules(self, event, rule):
        ip_string = get_dotted_field_value(event, rule.source_fields[0])
        if self._handle_missing_fields(event, rule, rule.source_fields, [ip_string]):
            return
        geoip_data = self._try_getting_geoip_data(ip_string)
        if not geoip_data:
            return
        fields = {
            rule.customize_target_subfields.get(target, f"{rule.target_field}.{target}"): value
            for target, value in geoip_data.items()
        }
        add_fields_to(
            event,
            fields,
            rule=rule,
            merge_with_target=False,
            overwrite_target=rule.overwrite_target,
        )
