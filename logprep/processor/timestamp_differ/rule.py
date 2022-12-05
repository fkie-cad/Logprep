"""
TimestampDiffer
===============

# FIXME: Docu
The `timestamp_differ` ...

https://arrow.readthedocs.io/en/latest/guide.html#supported-tokens

"""
import re

from attr import field
from attrs import define, validators

from logprep.processor.field_manager.rule import FieldManagerRule

FIELD_PATTERN = r"\$\{([+&?]?[^${]*)\}"


class TimestampDifferRule(FieldManagerRule):
    @define(kw_only=True)
    class Config(FieldManagerRule.Config):
        """Config for TimestampDifferRule"""

        diff: str = field(
            validator=[
                validators.instance_of(str),
                validators.matches_re(rf"({FIELD_PATTERN} - {FIELD_PATTERN})"),
            ]
        )
        """tbd"""
        source_fields: list = field(factory=list)
        output_format: str = field(
            default="seconds",
            validator=[
                validators.instance_of(str),
                validators.in_(["seconds", "milliseconds", "nanoseconds"]),
            ],
        )

        def __attrs_post_init__(self):
            field_format_str = re.findall(FIELD_PATTERN, self.diff)
            field_format_tuple = []
            for field_format_description in field_format_str:
                field_format_split = field_format_description.split(":", maxsplit=1)
                if len(field_format_split) == 1:
                    field_format_split += [None]
                field_format_tuple.append(field_format_split)
            self.source_fields = field_format_tuple

    # pylint: disable=missing-function-docstring
    @property
    def diff(self):
        return self._config.diff

    @property
    def output_format(self):
        return self._config.output_format

    # pylint: enable=missing-function-docstring
