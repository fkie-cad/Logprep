"""This module is used to resolve domains."""

from logprep.filter.expression.filter_expression import FilterExpression

from logprep.processor.base.rule import Rule, InvalidRuleDefinitionError


class DomainResolverRuleError(InvalidRuleDefinitionError):
    """Base class for DomainResolver rule related exceptions."""

    def __init__(self, message: str):
        super().__init__(f'DomainResolver rule ({message}): ')


class InvalidDomainResolverDefinition(DomainResolverRuleError):
    """Raise if DomainResolver definition invalid."""

    def __init__(self, definition):
        message = f'The following DomainResolver definition is invalid: {definition}'
        super().__init__(message)


class DomainResolverRule(Rule):
    """Check if documents match a filter."""

    def __init__(self, filter_rule: FilterExpression, domain_resolver_cfg: dict):
        super().__init__(filter_rule)

        self._source_url_or_domain = domain_resolver_cfg['source_url_or_domain']

    def __eq__(self, other: 'DomainResolverRule') -> bool:
        return (other.filter == self._filter) and \
               (self._source_url_or_domain == other.source_url_or_domain)

    def __hash__(self) -> int:
        return hash(repr(self))

    # pylint: disable=C0111
    @property
    def source_url_or_domain(self) -> str:
        return self._source_url_or_domain
    # pylint: enable=C0111

    @staticmethod
    def _create_from_dict(rule: dict) -> 'DomainResolverRule':
        DomainResolverRule._check_rule_validity(rule, 'domain_resolver')
        DomainResolverRule._check_if_valid(rule)

        filter_expression = Rule._create_filter_expression(rule)
        return DomainResolverRule(filter_expression, rule['domain_resolver'])

    @staticmethod
    def _check_if_valid(rule: dict):
        domain_resolver_cfg = rule['domain_resolver']
        for field in ('source_url_or_domain',):
            if not isinstance(domain_resolver_cfg[field], str):
                raise InvalidDomainResolverDefinition('"{}" value "{}" is not a dict!'.format(
                                                field, domain_resolver_cfg[field]))
