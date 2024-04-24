"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

A speaking example:

..  code-block:: yaml
    :linenos:
    :caption: Given grokker rule

    filter: message
    grokker:
        mapping:
            message: "%{TIMESTAMP_ISO8601:@timestamp} %{LOGLEVEL:logLevel} %{GREEDYDATA:logMessage}"
    description: 'an example log message'

..  code-block:: json
    :linenos:
    :caption: Incoming event

    {"message": "2020-07-16T19:20:30.45+01:00 DEBUG This is a sample log"}

..  code-block:: json
    :linenos:
    :caption: Processed event

    {
        "message": "2020-07-16T19:20:30.45+01:00 DEBUG This is a sample log",
        "@timestamp": "2020-07-16T19:20:30.45+01:00",
        "logLevel": "DEBUG",
        "logMessage": "This is a sample log"
    }


.. autoclass:: logprep.processor.grokker.rule.GrokkerRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:

Examples for grokker:
------------------------------------------------

.. datatemplate:import-module:: tests.unit.processor.grokker.test_grokker
   :template: testcase-renderer.tmpl

"""

import re

from attrs import define, field, validators

from logprep.processor.base.exceptions import InvalidRuleDefinitionError
from logprep.processor.dissector.rule import DissectorRule
from logprep.util.grok.grok import GROK, ONIGURUMA, Grok
from logprep.util.helper import get_dotted_field_list

NOT_GROK = rf"(?!({GROK})|({ONIGURUMA})).*"
MAPPING_VALIDATION_REGEX = re.compile(rf"^(({NOT_GROK})?(({GROK})|({ONIGURUMA}))({NOT_GROK})?)*$")

FIELD_PATTERN = re.compile(r"%\{[A-Z0-9_]*?:([^\[\]]*?)(:.*)?\}")


def _dotted_field_to_logstash_converter(mapping: dict) -> dict:
    if not mapping:
        return mapping

    def _transform(pattern):  # nosemgrep
        fields = re.findall(FIELD_PATTERN, pattern)
        for dotted_field, _ in fields:
            if "." in dotted_field:
                replacement = "".join(f"[{element}]" for element in dotted_field.split("."))
                # ensure full field is replaced by scanning for ':' at the front and '}' or ':'
                # at the end in the pattern. Also add them again in the replacement string.
                pattern = re.sub(
                    f":{re.escape(dotted_field)}([}}:])", f":{replacement}\\1", pattern
                )
        return pattern

    def _replace_pattern(pattern):
        if isinstance(pattern, list):
            pattern = list(map(_transform, pattern))
        else:
            pattern = [_transform(pattern)]
        return pattern

    return {dotted_field: _replace_pattern(pattern) for dotted_field, pattern in mapping.items()}


class GrokkerRule(DissectorRule):
    """grokker rule"""

    @define(kw_only=True)
    class Config(DissectorRule.Config):
        """Config for GrokkerRule"""

        mapping: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.deep_iterable(
                        member_validator=validators.matches_re(MAPPING_VALIDATION_REGEX),
                        iterable_validator=validators.instance_of(list),
                    ),
                ),
                validators.deep_iterable(
                    member_validator=validators.instance_of(str),
                    iterable_validator=validators.min_len(1),
                ),
            ],
            converter=_dotted_field_to_logstash_converter,
        )
        """A mapping from source fields to a grok pattern.
        Dotted field notation is possible in key and in the grok pattern.
        Additionally logstash field notation is possible in grok pattern.
        The value can be a list of search patterns or a single search pattern.
        Lists of search pattern will be checked in the order of the list until the first matching
        pattern.
        It is possible to use `oniguruma` regex pattern with or without grok patterns in the
        patterns part. When defining an `oniguruma` there is a limitation of three nested
        parentheses inside the pattern. Applying more nested parentheses is not possible.
        Logstashs ecs conform grok patterns are used to resolve the here used grok patterns.
        When writing patterns it is advised to be careful as the underlying regex can become complex
        fast. If the execution and the resolving of the pattern takes more than one second a
        matching timeout will be raised.
        """
        patterns: dict = field(
            validator=[
                validators.instance_of(dict),
                validators.deep_mapping(
                    key_validator=validators.instance_of(str),
                    value_validator=validators.instance_of(str),
                ),
            ],
            factory=dict,
        )
        r"""(Optional) additional grok patterns as mapping. E.g. :code:`CUSTOM_PATTERN: [^\s]*`
        if you want to use special target fields, you are able to use them an usual in the
        mapping sections. Here you only have to declare the matching regex without named groups.
        """

    actions: dict[str, Grok]

    def _set_mapping_actions(self):
        self.actions = {}

    def _set_convert_actions(self):
        pass

    def set_mapping_actions(self, custom_patterns_dir: str = None) -> None:
        """sets the mapping actions"""
        custom_patterns_dir = "" if custom_patterns_dir is None else custom_patterns_dir

        try:
            self.actions = {
                dotted_field: Grok(
                    pattern,
                    custom_patterns=self._config.patterns,
                    custom_patterns_dir=custom_patterns_dir,
                )
                for dotted_field, pattern in self._config.mapping.items()
            }
        except re.error as error:
            raise InvalidRuleDefinitionError(
                f"The resolved grok pattern '{error.pattern}' is not valid"
            )

        # to ensure no string splitting is done during processing for target fields:
        for _, grok in self.actions.items():
            target_fields = list(grok.field_mapper.values())
            if not target_fields:
                raise InvalidRuleDefinitionError("no target fields defined")
            for target_field in target_fields:
                get_dotted_field_list(target_field)
