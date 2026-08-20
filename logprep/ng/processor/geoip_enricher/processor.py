"""
|PROCESSOR_NAME|
================

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

import asyncio
import logging
import tempfile
import typing
from ipaddress import ip_address
from pathlib import Path

from attrs import define, field, validators
from filelock import AsyncFileLock
from geoip2 import database
from geoip2.errors import AddressNotFoundError

from logprep.ng.processor.field_manager.processor import FieldManager
from logprep.ng.util.getter import GetterFactory
from logprep.processor.base.rule import Rule
from logprep.processor.geoip_enricher.rule import GEOIP_DATA_STUBS, GeoipEnricherRule
from logprep.util.helper import FieldValue, add_fields_to, get_dotted_field_value

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

    __slots__ = ["_city_db"]

    _city_db: database.Reader

    rule_class = GeoipEnricherRule

    @property
    def config(self) -> Config:
        """Provides the properly typed rule configuration object"""
        return typing.cast(GeoipEnricher.Config, self._config)

    async def _load_city_db(self) -> database.Reader:
        db_path = Path(self.config.db_path)

        if not await asyncio.to_thread(db_path.exists):
            logger.debug("start geoip database download...")

            logprep_tmp_dir = Path(tempfile.gettempdir()) / "logprep"
            await asyncio.to_thread(
                logprep_tmp_dir.mkdir,
                parents=True,
                exist_ok=True,
            )

            db_path_file = logprep_tmp_dir / f"{self.name}.mmdb"
            lock = AsyncFileLock(str(db_path_file) + ".lock")

            async with lock:
                if not await asyncio.to_thread(db_path_file.exists):
                    tmp = db_path_file.with_suffix(".tmp")
                    getter = GetterFactory.from_string(self.config.db_path)
                    raw = await getter.get_raw()
                    await asyncio.to_thread(tmp.write_bytes, raw)
                    await asyncio.to_thread(tmp.replace, db_path_file)

            db_path = db_path_file
            logger.debug("finished geoip database download.")

        try:
            return await asyncio.to_thread(database.Reader, db_path)
        except Exception:
            logger.exception("failed to load GeoIP database")
            raise

    async def setup(self) -> None:
        await super().setup()
        self._city_db = await self._load_city_db()

    async def _try_getting_geoip_data(self, ip_string: str) -> dict:
        try:
            ip_addr = str(ip_address(ip_string))
            ip_data = await asyncio.to_thread(
                self._city_db.city,
                ip_addr,
            )

            geoip_data = GEOIP_DATA_STUBS.copy()

            geoip_data |= {
                "properties.accuracy_radius": ip_data.location.accuracy_radius,
            }

            geoip_data |= {
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

    async def _apply_rules(self, event: dict[str, FieldValue], rule: Rule) -> None:
        rule = typing.cast(GeoipEnricherRule, rule)
        ip_string = get_dotted_field_value(event, rule.source_fields[0])
        if self._handle_missing_fields(event, rule, rule.source_fields, [ip_string]):
            return
        if not isinstance(ip_string, str):
            raise ValueError("ip_string is not a string type")
        geoip_data = await self._try_getting_geoip_data(ip_string)
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

    async def has_asyncio(self) -> bool:
        """Return whether the processor performs asynchronous I/O operations."""
        return True
