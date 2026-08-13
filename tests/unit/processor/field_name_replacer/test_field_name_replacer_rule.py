# pylint: disable=missing-docstring
import pytest

from logprep.processor.field_name_replacer.rule import FieldNameReplacerRule


class TestFieldNameReplacerRule:
    @staticmethod
    def rule(config):
        return {
            "filter": "test",
            "field_name_replacer": {
                "source_fields": ["test"],
                "to_replace": ".",
                "replacement": "__",
                **config,
            },
        }

    def test_create_from_dict_returns_field_name_replacer_rule(self):
        rule = FieldNameReplacerRule.create_from_dict(self.rule({}))

        assert isinstance(rule, FieldNameReplacerRule)

    @pytest.mark.parametrize(
        "config, error",
        [
            ({"source_fields": "test"}, TypeError),
            ({"source_fields": [""]}, ValueError),
            ({"to_replace": []}, ValueError),
            ({"to_replace": [".", ""]}, ValueError),
            ({"collision_strategy": "replace"}, ValueError),
        ],
    )
    def test_create_from_dict_validates_config(self, config, error):
        with pytest.raises(error):
            FieldNameReplacerRule.create_from_dict(self.rule(config))

    def test_create_from_dict_accepts_multiple_values_to_replace(self):
        rule = FieldNameReplacerRule.create_from_dict(self.rule({"to_replace": [".", "/"]}))

        assert rule.config.to_replace == [".", "/"]
