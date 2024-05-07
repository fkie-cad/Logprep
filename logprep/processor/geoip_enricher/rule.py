"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The geoip enricher requires the additional field :code:`geoip`.
The default output_field can be overridden using the optional parameter
:code:`target_field`. This can be a dotted subfield.
The additional field :code:`geoip.source_fields` must be given as list with one element.
It contains the IP for which the geoip data should be added.

In the following example the IP in :code:`client.ip` will be enriched with geoip data.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: client.ip
    geoip:
      source_fields: [client.ip]
    description: '...'

.. autoclass:: logprep.processor.geoip_enricher.rule.GeoipEnricherRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

from attr import Factory
from attrs import define, field, validators

from logprep.processor.field_manager.rule import FieldManagerRule

GEOIP_DATA_STUBS = {
    "type": "Feature",
    "geometry.type": None,
    "geometry.coordinates": None,
    "properties.accuracy_radius": None,
    "properties.continent": None,
    "properties.continent_code": None,
    "properties.country": None,
    "properties.country_iso_code": None,
    "properties.time_zone": None,
    "properties.city": None,
    "properties.postal_code": None,
    "properties.subdivision": None,
}


class GeoipEnricherRule(FieldManagerRule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """RuleConfig for GeoipEnricher"""

        source_fields: list = field(
            validator=[
                validators.instance_of(list),
                validators.deep_iterable(member_validator=validators.instance_of(str)),
                validators.min_len(1),
                validators.max_len(1),
            ],
            default=[],
        )
        """Field to get geoip information for."""
        target_field: str = field(validator=validators.instance_of(str), default="geoip")
        """Field for the output information. Defaults to :code:`geoip`."""
        customize_target_subfields: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.and_(
                        validators.instance_of(str),
                        validators.in_(GEOIP_DATA_STUBS.keys()),
                    ),
                    value_validator=validators.instance_of(str),
                ),
            ],
            default=Factory(dict),
        )
        """(Optional) Rewrites the default output subfield locations to custom output subfield
        locations. Must be in the form of key value mapping pairs
        (e.g. :code:`default_output: custom_output`). Following default outputs can be customized:

        .. datatemplate:import-module:: logprep.processor.geoip_enricher.rule

            {% for item in data.GEOIP_DATA_STUBS.keys() %}
                * :code:`{{ item }}`
            {% endfor %}

        A concrete example would look like this:

        ..  code-block:: yaml
            :linenos:

            filter: client.ip
            geoip:
              source_fields: [client.ip]
              customize_target_subfields:
                geometry.type: client.geo.type
                geometry.coordinates: client.geo.coordinates
            description: '...'
        """
        mapping: dict = field(default="", init=False, repr=False, eq=False)
        ignore_missing_fields: bool = field(default=False, init=False, repr=False, eq=False)

    @property
    def customize_target_subfields(self) -> dict:  # pylint: disable=missing-function-docstring
        return self._config.customize_target_subfields
