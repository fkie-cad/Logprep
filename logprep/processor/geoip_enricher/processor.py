"""
GeoipEnricher
-------------
Processor to enrich log messages with geolocalization information

Example
^^^^^^^
..  code-block:: yaml
    :linenos:

    - geoipenrichername:
        type: geoip_enricher
        specific_rules:
            - tests/testdata/geoip_enricher/rules/
        generic_rules:
            - tests/testdata/geoip_enricher/rules/
        db_path: /path/to/GeoLite2-City.mmdb
"""
from functools import cached_property
from ipaddress import ip_address
from pathlib import Path
from multiprocessing import current_process

from attr import define, field, validators
from geoip2 import database
from geoip2.errors import AddressNotFoundError

from logprep.abc.processor import Processor
from logprep.processor.base.exceptions import DuplicationError
from logprep.processor.geoip_enricher.rule import GeoipEnricherRule, GEOIP_DATA_STUBS
from logprep.util.helper import add_field_to, get_dotted_field_value
from logprep.util.getter import GetterFactory


class GeoipEnricher(Processor):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(Processor.Config):
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
        return database.Reader(self._config.db_path)

    def setup(self):
        super().setup()
        db_path = Path(self._config.db_path)
        if not db_path.exists():
            self._logger.debug("start geoip database download...")
            db_path_file = Path(f"{current_process().name}-{self.name}.mmdb")
            db_path_file.touch()
            db_path_file.write_bytes(GetterFactory.from_string(str(self._config.db_path)).get_raw())
            self._logger.debug("finished geoip database download.")
            self._config.db_path = str(db_path_file.absolute())

    def _try_getting_geoip_data(self, ip_string):
        try:
            ip_addr = str(ip_address(ip_string))
            ip_data = self._city_db.city(ip_addr)
            geoip_data = GEOIP_DATA_STUBS.copy()
            geoip_data.update(
                {
                    "geometry.coordinates": [
                        ip_data.location.longitude,
                        ip_data.location.latitude,
                    ],
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
            )
            return geoip_data
        except (ValueError, AddressNotFoundError):
            return {}

    def _apply_rules(self, event, rule):
        ip_string = get_dotted_field_value(event, rule.source_fields[0])
        geoip_data = self._try_getting_geoip_data(ip_string)
        if not geoip_data:
            return
        for target_subfield, value in geoip_data.items():
            if value is None:
                continue
            full_output_field = f"{rule.target_field}.{target_subfield}"
            if target_subfield in rule.customize_target_subfields:
                full_output_field = rule.customize_target_subfields.get(target_subfield)
            adding_was_successful = add_field_to(
                event=event,
                output_field=full_output_field,
                content=value,
                extends_lists=False,
                overwrite_output_field=rule.overwrite_target,
            )
            if not adding_was_successful:
                raise DuplicationError(self.name, [full_output_field])
