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
from typing import List

from attr import define, field
from geoip2 import database
from geoip2.errors import AddressNotFoundError

from logprep.abc import Processor
from logprep.processor.geoip_enricher.rule import GeoipEnricherRule
from logprep.util.helper import add_field_to, get_dotted_field_value
from logprep.util.validators import url_validator


class GeoipEnricherError(BaseException):
    """Base class for GeoipEnricher related exceptions."""

    def __init__(self, name: str, message: str):
        super().__init__(f"GeoipEnricher ({name}): {message}")


class DuplicationError(GeoipEnricherError):
    """Raise if field already exists."""

    def __init__(self, name: str, skipped_fields: List[str]):
        message = (
            "The following fields already existed and "
            "were not overwritten by the GeoipEnricher: "
        )
        message += " ".join(skipped_fields)

        super().__init__(name, message)


class GeoipEnricher(Processor):
    """Resolve values in documents by referencing a mapping list."""

    @define(kw_only=True)
    class Config(Processor.Config):
        """geoip_enricher config"""

        db_path: str = field(validator=url_validator)
        """Path to a `Geo2Lite` city database by `Maxmind` in binary format.
            This must be downloaded separately.
            This product includes GeoLite2 data created by MaxMind, available from
            https://www.maxmind.com."""

    __slots__ = []

    rule_class = GeoipEnricherRule

    @cached_property
    def _city_db(self):
        return database.Reader(self._config.db_path)

    def _try_getting_geoip_data(self, ip_string):
        try:
            ip_addr = str(ip_address(ip_string))
            ip_data = self._city_db.city(ip_addr)
            geoip_data = {
                "type": "Feature",
                "geometry.coordinates": [
                    ip_data.location.longitude,
                    ip_data.location.latitude,
                ],
                "geometry.type": "Point",
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
            return geoip_data
        except (ValueError, AddressNotFoundError):
            return {}

    def _apply_rules(self, event, rule):
        ip_string = get_dotted_field_value(event, rule.source_fields[0])
        geoip_data = self._try_getting_geoip_data(ip_string)
        if not geoip_data:
            return
        for target_subfield, value in geoip_data.items():
            if not value:
                continue
            full_output_field = f"{rule.target_field}.{target_subfield}"
            if target_subfield in rule.customize_target_subfields.keys():
                full_output_field = rule.customize_target_subfields[target_subfield]
            adding_was_successful = add_field_to(
                event, full_output_field, value, overwrite_output_field=rule.overwrite_target
            )
            if not adding_was_successful:
                raise DuplicationError(self.name, [full_output_field])
