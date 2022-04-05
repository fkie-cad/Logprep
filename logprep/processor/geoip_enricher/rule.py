"""This module is used to resolve field values from documents via a list."""

from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError


class GeoIPEnricherRuleError(InvalidRuleDefinitionError):
    """Base class for GeoIPEnricher rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f"GeoIPEnricher rule ({message}): ")


class InvalidGeoIPEnricherDefinition(GeoIPEnricherRuleError):
    """Raise if GeoIPEnricher definition invalid."""

    def __init__(self, definition):
        message = f"The following GeoIPEnricher definition is invalid: {definition}"
        super().__init__(message)


class GeoIPEnricherRule(Rule):
    """Check if documents match a filter."""

    def __init__(self, filter_rule: FilterExpression, geoip_enricher_cfg: dict):
        super().__init__(filter_rule)

        if "output_field" in geoip_enricher_cfg.keys():
            self._output_field = geoip_enricher_cfg["output_field"]
        else:
            self._output_field = "geoip"

        self._source_ip = geoip_enricher_cfg["source_ip"]

    def __eq__(self, other: "GeoIPEnricherRule") -> bool:
        return (other.filter == self._filter) and (self.source_ip == other.source_ip)

    def __hash__(self) -> int:
        return hash(repr(self))

    # pylint: disable=C0111
    @property
    def source_ip(self) -> dict:
        return self._source_ip

    # pylint: enable=C0111

    @property
    def output_field(self) -> dict:
        return self._output_field

    @staticmethod
    def _create_from_dict(rule: dict) -> "GeoIPEnricherRule":
        GeoIPEnricherRule._check_rule_validity(rule, "geoip_enricher")
        GeoIPEnricherRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return GeoIPEnricherRule(filter_expression, rule["geoip_enricher"])

    @staticmethod
    def _check_if_valid(rule: dict):
        geoip_enricher_cfg = rule["geoip_enricher"]
        for field in ("source_ip",):
            if not isinstance(geoip_enricher_cfg[field], str):
                raise InvalidGeoIPEnricherDefinition(
                    '"{}" value "{}" is not a string!'.format(field, geoip_enricher_cfg[field])
                )
        if "output_field" in geoip_enricher_cfg.keys():
            for field in ("output_field",):
                if not isinstance(geoip_enricher_cfg[field], str):
                    raise InvalidGeoIPEnricherDefinition(
                        '"{}" value "{}" is not a string!'.format(field, geoip_enricher_cfg[field])
                    )
