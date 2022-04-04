from copy import deepcopy
from os.path import join
from logging import getLogger

from pytest import raises, importorskip

importorskip("logprep.processor.labeler")

from unittest.mock import patch

from logprep.input.dummy_input import DummyInput
from logprep.processor.labeler.exceptions import *
from logprep.processor.base.exceptions import *
from logprep.processor.labeler.factory import Labeler, LabelerFactory
from logprep.processor.base.processor import RuleBasedProcessor
from logprep.processor.processor_factory_error import (
    UnknownProcessorTypeError,
    InvalidConfigurationError,
)
from logprep.processor.labeler.rule import LabelingRule
from logprep.processor.labeler.labeling_schema import LabelingSchema
from tests.testdata.metadata import (
    path_to_single_rule,
    path_to_invalid_rules,
    path_to_schema,
    path_to_schema2,
    path_to_testdata,
    path_to_rules2,
)
from tests.testdata.ruledata import simple_rule

logger = getLogger()


class TestLabelerFactory:
    _config = {"type": "labeler", "schema": path_to_schema, "rules": [path_to_single_rule]}

    def setup_method(self, name):
        self.config = deepcopy(self._config)

    def test_create_fails_when_type_is_not_labeler(self):
        for not_labeler in [None, "test", "almost labeler", "labelerer", "unknown"]:
            config = deepcopy(self.config)
            config["type"] = not_labeler
            with raises(UnknownProcessorTypeError):
                LabelerFactory.create("name", config, logger)

    def test_create_fails_when_config_does_not_contain_rules(self):
        del self.config["rules"]
        with raises(
            RulesDefinitionMissingError,
            match="The labeler configuration must contain at least one path to a rules directory.",
        ):
            LabelerFactory.create("name", self.config, logger)

    def test_create_fails_when_config_does_not_contain_schema(self):
        del self.config["schema"]
        with raises(
            SchemaDefinitionMissingError,
            match="The labeler configuration must point to a schema definition.",
        ):
            LabelerFactory.create("name", self.config, logger)

    def test_create_fails_when_schema_config_points_to_non_existing_file(self):
        self.config["schema"] = join("path", "to", "non-existing", "file")
        with raises(
            InvalidSchemaDefinitionError,
            match='schema does not point to a schema definition file: Not a valid schema file: File not found: ".*".',
        ):
            LabelerFactory.create("name", self.config, logger)

    def test_create_fails_when_schema_config_points_to_directory(self):
        self.config["schema"] = path_to_testdata
        with raises(InvalidSchemaDefinitionError, match="Is a directory:"):
            LabelerFactory.create("name", self.config, logger)

    def test_create_fails_when_include_parent_labels_is_not_boolean(self):
        self.config["include_parent_labels"] = "this is a string"
        with raises(
            InvalidIncludeParentsValueError,
            match='"include_parent_labels" must be either true or false.',
        ):
            LabelerFactory.create("name", self.config, logger)

    def test_create_fails_when_rules_points_to_file(self):
        self.config["rules"].append(path_to_schema)
        with raises(InvalidRuleConfigurationError, match='Not a rule directory: ".*"'):
            LabelerFactory.create("name", self.config, logger)

    def test_create_fails_when_rules_path_contains_an_invalid_file(self):
        self.config["rules"].append(path_to_invalid_rules)
        with raises(InvalidRuleConfigurationError, match='Invalid rule file ".*".'):
            LabelerFactory.create("name", self.config, logger)

    def test_create_fails_when_rules_do_not_conform_to_labeling_schema(self):
        self.config["schema"] = path_to_schema2
        with raises(InvalidRuleConfigurationError, match="Does not conform to labeling schema"):
            LabelerFactory.create("name", self.config, logger)

    def test_create_only_raises_factory_errors(self):
        # Note: This will have to be maintained manually anyway; checking the
        # classes implies less code duplication than triggering the exceptions
        assert issubclass(RulesDefinitionMissingError, InvalidConfigurationError)
        assert issubclass(SchemaDefinitionMissingError, InvalidConfigurationError)
        assert issubclass(InvalidIncludeParentsValueError, InvalidConfigurationError)
        assert issubclass(InvalidRuleConfigurationError, InvalidConfigurationError)

    def test_create_assigns_the_given_name_to_the_labeler(self):
        labeler = LabelerFactory.create("name", self.config, logger)

        assert labeler._name == "name"

    def test_create_loads_the_specified_labeling_schema(self):
        expected_schema = LabelingSchema.create_from_file(path_to_schema)
        labeler = LabelerFactory.create("name", self.config, logger)

        assert labeler._schema == expected_schema

    def test_create_loads_the_specified_rules(self):
        expected_rule = LabelingRule._create_from_dict(simple_rule[0])
        labeler = LabelerFactory.create("name", self.config, logger)

        assert labeler._tree._root._children[0]._children[0].matching_rules == [expected_rule]


class TestLabeler:
    timeout = 0.01

    def setup_class(self):
        self.labeler_name = "Test Labeler Name"
        self.schema = LabelingSchema()
        self.schema.ingest_schema(
            {
                "reporter": {
                    "category": "category description",
                    "windows": {"description": "windows description"},
                }
            }
        )

        self.expanded_schema = LabelingSchema()
        self.expanded_schema.ingest_schema(
            {
                "reporter": {
                    "category": "category description",
                    "parentlabel": {
                        "description": "parentlabel description",
                        "windows": {"description": "windows description"},
                    },
                }
            }
        )

        self.emtpy_schema = LabelingSchema()
        self.emtpy_schema.ingest_schema({})

        self.labeler = Labeler(self.labeler_name, None, logger)
        self.labeler.set_labeling_scheme(self.schema)
        self.labeler.add_rules_from_directory([path_to_single_rule])

    def test_is_a_processor_implementation(self):
        assert isinstance(Labeler(self.labeler_name, None, logger), RuleBasedProcessor)

    def test_setup_fails_when_schema_is_unset(self):
        labeler = Labeler(self.labeler_name, None, logger)

        with raises(
            NoLabelingSchemeDefinedError,
            match="Labeler \\(%s\\): No labeling schema was loaded." % self.labeler_name,
        ):
            labeler.setup()

    def test_setup_fails_no_rules_were_loaded(self):
        labeler = Labeler(self.labeler_name, None, logger)
        labeler.set_labeling_scheme(self.schema)

        with raises(
            MustLoadRulesFirstError,
            match="Labeler \\(%s\\): No rules were loaded." % self.labeler_name,
        ):
            labeler.setup()

    def test_cannot_set_schema_set_to_non_schema_object(self):
        for non_ruleset in [None, "string", 42, [], {}, DummyInput([])]:
            with raises(
                InvalidLabelingSchemaError,
                match="Labeler \\(%s\\): Not a labeling schema: .*" % self.labeler_name,
            ):
                self.labeler.set_labeling_scheme(non_ruleset)

    def test_process_fails_if_no_rules_were_loaded(self):
        labeler = Labeler(self.labeler_name, None, logger)
        with raises(MustLoadRulesFirstError):
            labeler.process({})

    @patch("logprep.processor.labeler.rule.LabelingRule.add_labels")
    def test_process_fails_on_rule_error(self, mock_rule):
        document = {"applyrule": "yes"}
        mock_rule.side_effect = RuleError("Some rule error.")
        with raises(RuleError, match="Some rule error."):
            self.labeler.process(document)

    def test_process_adds_labels_to_event(self):
        document = {"applyrule": "yes"}
        expected = {"applyrule": "yes", "label": {"reporter": ["windows"]}}
        self.labeler.process(document)

        assert document == expected

    def test_process_adds_labels_to_event_with_umlauts(self):
        document = {"äpplyrüle": "nö"}
        expected = {"äpplyrüle": "nö", "label": {"räpörter": ["windöws"]}}

        rule_dict = {
            "filter": "äpplyrüle: nö",
            "label": {"räpörter": ["windöws"]},
            "description": "this is ä test rüle",
        }
        rule = LabelingRule._create_from_dict(rule_dict)
        self.labeler._tree.add_rule(rule, logger)
        self.labeler.ps.setup_rules([None] * self.labeler._tree.rule_counter)

        self.labeler.process(document)

        assert document == expected

    def test_process_adds_labels_including_parents_when_flag_was_set(self):
        labeler = Labeler(self.labeler_name, None, logger)
        labeler.set_labeling_scheme(self.expanded_schema)
        labeler.add_rules_from_directory([path_to_single_rule], include_parent_labels=True)

        document = {"applyrule": "yes"}
        expected = {"applyrule": "yes", "label": {"reporter": ["parentlabel", "windows"]}}
        labeler.process(document)

        assert document == expected

    def test_cannot_add_rules_if_labeling_scheme_is_unset(self):
        labeler = Labeler(self.labeler_name, None, logger)

        with raises(
            NoLabelingSchemeDefinedError,
            match="Labeler \\(%s\\): No labeling schema was loaded." % self.labeler_name,
        ):
            labeler.add_rules_from_directory([path_to_single_rule])

    def test_add_rules_fails_if_path_points_to_file(self):
        self.labeler.set_labeling_scheme(self.emtpy_schema)

        with raises(
            NotARulesDirectoryError,
            match=r'\'%s\', \'Not a rule directory: ".*"\'.*' % self.labeler_name,
        ):
            self.labeler.add_rules_from_directory([path_to_schema])

    def test_cannot_add_rules_that_violate_labeling_scheme(self):
        self.labeler.set_labeling_scheme(self.emtpy_schema)

        with raises(
            RuleDoesNotConformToLabelingSchemaError,
            match='Labeler \\(%s\\): Invalid rule file ".*": Does not conform to labeling schema.'
            % self.labeler_name,
        ):
            self.labeler.add_rules_from_directory([path_to_single_rule])

    def test_fails_when_trying_to_load_invalid_rule_file(self):
        self.labeler.set_labeling_scheme(self.emtpy_schema)

        with raises(
            InvalidRuleFileError, match=r'\'%s\', \'Invalid rule file ".*".*.' % self.labeler_name
        ):
            self.labeler.add_rules_from_directory([path_to_invalid_rules])

    def test_cannot_set_labeling_scheme_to_non_scheme_object(self):
        for non_scheme in [None, "string", 42, [], {}]:
            with raises(InvalidLabelingSchemaError):
                self.labeler.set_labeling_scheme(non_scheme)

    def test_rules_contains_expected_rules_after_adding_from_directory(self):
        expected_rule = LabelingRule._create_from_dict(simple_rule[0])
        labeler = Labeler(self.labeler_name, None, logger)
        labeler.set_labeling_scheme(self.schema)
        labeler.add_rules_from_directory([path_to_single_rule])

        assert labeler._tree.rule_counter == 1
        assert labeler._tree._root._children[0].children[0].matching_rules == [expected_rule]

    def test_add_labels_changes_nothing_for_empty_event(self):
        event = {}
        self.labeler.process(event)

        assert len(event) == 0

    def test_add_labels_adds_labels_for_matching_rules(self):
        event = {"applyrule": "yes"}
        self.labeler.process(event)

        assert event["label"] == {"reporter": ["windows"]}

    def test_labels_are_always_stored_in_alphabetical_order(self):
        labeler = Labeler(self.labeler_name, None, logger)
        labeler.set_labeling_scheme(self.expanded_schema)
        labeler.add_rules_from_directory([path_to_single_rule], include_parent_labels=True)

        for _ in range(75):
            # simply calling list() on the set of labels usually stores the labels in the correct order
            # but it is not guaranteed, so this test should fail at least once in a while (unless the
            # labels are really sorted)
            event = {"applyrule": "yes"}
            labeler.process(event)

            assert event["label"]["reporter"] == ["parentlabel", "windows"]

    def test_multiple_labelers_just_add_more_labels(self):
        labeler = Labeler(self.labeler_name, None, logger)
        labeler.set_labeling_scheme(self.expanded_schema)
        labeler.add_rules_from_directory([path_to_single_rule])

        labeler2 = Labeler("test2", None, logger)
        labeler2.set_labeling_scheme(self.expanded_schema)
        labeler2.add_rules_from_directory([path_to_rules2])

        event = {"applyrule": "yes"}
        labeler.process(event)
        labeler2.process(event)

        assert event["label"]["reporter"] == ["parentlabel", "windows"]

    def test_process_matches_event_with_array_with_one_element(self):
        document = {"field_with_array": ["im_inside_an_array"]}
        expected = {
            "field_with_array": ["im_inside_an_array"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        rule_dict = {
            "filter": "field_with_array: im_inside_an_array",
            "label": {"some_new_label": ["some_new_value"]},
            "description": "This does even match with arrays!",
        }

        rule = LabelingRule._create_from_dict(rule_dict)
        self.labeler._tree.add_rule(rule, logger)
        self.labeler.ps.setup_rules([None] * self.labeler._tree.rule_counter)

        self.labeler.process(document)

        assert document == expected

    def test_process_matches_event_with_array_if_at_least_one_element_matches(self):
        document = {"field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"]}
        expected = {
            "field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        rule_dict = {
            "filter": "field_with_array: im_inside_an_array",
            "label": {"some_new_label": ["some_new_value"]},
            "description": "This does even match with arrays!",
        }

        rule = LabelingRule._create_from_dict(rule_dict)
        self.labeler._tree.add_rule(rule, logger)
        self.labeler.ps.setup_rules([None] * self.labeler._tree.rule_counter)

        self.labeler.process(document)

        assert document == expected

    def test_process_matches_event_with_array_with_one_element_with_regex(self):
        document = {"field_with_array": ["im_inside_an_array"]}
        expected = {
            "field_with_array": ["im_inside_an_array"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        rule_dict = {
            "filter": "field_with_array: im_inside_an_a.*y",
            "regex_fields": ["field_with_array"],
            "label": {"some_new_label": ["some_new_value"]},
            "description": "This does even match with arrays!",
        }

        rule = LabelingRule._create_from_dict(rule_dict)
        self.labeler._tree.add_rule(rule, logger)
        self.labeler.ps.setup_rules([None] * self.labeler._tree.rule_counter)

        self.labeler.process(document)

        assert document == expected

    def test_process_matches_event_with_array_with_one_element_with_regex_one_without(self):
        document = {"field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"]}
        expected = {
            "field_with_array": ["im_inside_an_array", "im_also_inside_that_array!"],
            "label": {"some_new_label": ["some_new_value"]},
        }

        rule_dict = {
            "filter": "field_with_array: im_inside_.*y AND field_with_array: im_also_inside_that_array",
            "regex_fields": ["field_with_array"],
            "label": {"some_new_label": ["some_new_value"]},
            "description": "This does even match with arrays!",
        }

        rule = LabelingRule._create_from_dict(rule_dict)
        self.labeler._tree.add_rule(rule, logger)
        self.labeler.ps.setup_rules([None] * self.labeler._tree.rule_counter)

        self.labeler.process(document)

        assert document == expected
