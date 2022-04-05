# pylint: disable=protected-access
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=wrong-import-position
# pylint: disable=wrong-import-order
from copy import deepcopy
from os.path import join

from pytest import raises, fail, importorskip

importorskip("logprep.processor.labeler")

from logprep.processor.labeler.labeling_schema import (
    InvalidLabelingSchemaFileError,
    LabelingSchemaError,
    LabelingSchema,
)
from logprep.processor.base.exceptions import (
    KeyDoesnotExistInSchemaError,
    ValueDoesnotExistInSchemaError,
)
from tests.testdata.FilledTempFile import JsonTempFile
from tests.testdata.metadata import path_to_testdata, path_to_config, path_to_schema


class SchemasForTests:
    deep_schema = {
        "reporter": {
            "category": "The event's reporter",
            "operatingsystem": {
                "description": 'This has a description to check whether the label is added despite a "hole" in the tree pointing to it',
                "unixlike": {
                    "linux": {
                        "description": "Linux",
                        "android": {"description": "Android operating system for mobile devices"},
                    }
                },
            },
        }
    }

    minimal_schema = {
        "reporter": {
            "category": "The event's reporter",
            "windows": {"description": "the description may actually be empty"},
        }
    }

    invalid_schema_category_without_category_field = {
        "reporter": {
            "category": "The event's reporter",
            "windows": {"description": "the description may actually be empty"},
        },
        "invalid": {"valid label": {"description": "this label is valid, the category is not"}},
    }

    invalid_schema_category_with_non_string_category_field = {
        "reporter": {
            "category": 42,
            "windows": {"description": "the description may actually be empty"},
        },
    }

    invalid_schema_category_with_non_description_leaf = {
        "reporter": {
            "category": "The event's reporter",
            "windows": {"description": "the description may actually be empty"},
        },
        "valid": {
            "category": "The category is valid, the label is not",
            "no description": {"key": "value"},
        },
    }

    invalid_schema_with_duplicate_label_in_same_category = {
        "reporter": {
            "category": "The event's reporter",
            "windows": {"description": "the description may actually be empty"},
            "valid": {"windows": {"description": "invalid, duplicate label"}},
        },
    }

    invalid_schema_with_description_in_top_level = {
        "reporter": {
            "category": "The event's reporter",
            "windows": {"description": "the description may actually be empty"},
        },
        "invalid": {
            "category": "This category has the necessary category entry",
            "description": "top level entries must not contain a description",
        },
    }


class TestLabelingSchemaCreateFromFile(SchemasForTests):
    def test_create_schema_fails_if_file_does_not_exist(self):
        with raises(
            InvalidLabelingSchemaFileError, match="Not a valid schema file: File not found: '.*'."
        ):
            LabelingSchema.create_from_file(join("path", "to", "non-existing", "file"))

    def test_create_schema_fails_if_path_points_to_directory(self):
        with raises(
            InvalidLabelingSchemaFileError,
            match=r"Not a valid schema file: \[Errno 21\] Is a directory: \'.*\'.",
        ):
            LabelingSchema.create_from_file(path_to_testdata)

    def test_create_schema_fails_is_file_not_valid_json(self):
        with JsonTempFile({}) as schema_file:
            with raises(
                InvalidLabelingSchemaFileError,
                match="Not a valid schema file: JSON decoder error: .*: '.*'.",
            ):
                LabelingSchema.create_from_file(path_to_config)

    def test_create_schema_fails_is_file_is_empty(self):
        with JsonTempFile({}) as schema_file:
            with raises(InvalidLabelingSchemaFileError, match="Not a valid schema file: '.*'."):
                LabelingSchema.create_from_file(schema_file)

    def test_fails_if_schema_contains_description_with_non_string_value(self):
        schema = deepcopy(self.minimal_schema)
        schema["reporter"]["key"] = {"description": None}

        for non_string in [123, 456.789, None]:
            schema["reporter"]["key"]["description"] = non_string

            self.assert_fails_with_expected_message(
                schema,
                "Not a valid schema file: Label 'key' does not have a valid description: '.*'.",
            )

    def test_accepts_schema_that_has_only_one_entry(self):
        try:
            with JsonTempFile(self.minimal_schema) as schema_file:
                LabelingSchema.create_from_file(schema_file)
        except InvalidLabelingSchemaFileError:
            fail("Did not accept a minimal schema")

    def test_rejects_schema_that_has_category_without_category_field(self):
        self.assert_fails_with_expected_message(
            self.invalid_schema_category_without_category_field,
            "Not a valid schema file: Category 'invalid' does not have a valid description: '.*'.",
        )

    def test_rejects_schema_that_has_non_string_category_field(self):
        self.assert_fails_with_expected_message(
            self.invalid_schema_category_with_non_string_category_field,
            "Not a valid schema file: Category 'reporter' does not have a valid description: '.*'.",
        )

    def test_rejects_schema_that_contains_non_description_leaf(self):
        self.assert_fails_with_expected_message(
            self.invalid_schema_category_with_non_description_leaf,
            r"Not a valid schema file: 'key' is a leaf but not a description: '.*'.",
        )

    def test_rejects_schema_with_duplicate_label_in_same_category(self):
        self.assert_fails_with_expected_message(
            self.invalid_schema_with_duplicate_label_in_same_category,
            "Not a valid schema file: Category 'reporter' contains label 'windows' more than once",
        )

    def assert_fails_with_expected_message(self, schema, error_message):
        with JsonTempFile(schema) as schema_file:
            with raises(InvalidLabelingSchemaFileError, match=error_message):
                LabelingSchema.create_from_file(schema_file)


class TestLabelingSchema(SchemasForTests):
    def setup_method(self, method_name):
        self.schema = LabelingSchema()

    def test_fails_if_schema_contains_description_with_non_string_value(self):
        schema = deepcopy(self.minimal_schema)
        schema["reporter"]["key"] = {"description": None}

        for non_string in [123, 456.789, None]:
            schema["reporter"]["key"]["description"] = non_string
            with raises(
                LabelingSchemaError,
                match="Label 'key' does not have a valid description",
            ):
                self.schema.ingest_schema(schema)

    def test_accepts_schema_that_has_only_one_entry(self):
        try:
            self.schema.ingest_schema(self.minimal_schema)
        except InvalidLabelingSchemaFileError:
            fail("Did not accept a minimal schema")

    def test_rejects_schema_that_has_category_without_category_field(self):
        with raises(
            LabelingSchemaError,
            match="Category 'invalid' does not have a valid description",
        ):
            self.schema.ingest_schema(self.invalid_schema_category_without_category_field)

    def test_rejects_schema_that_has_non_string_category_field(self):
        with raises(
            LabelingSchemaError,
            match="Category 'reporter' does not have a valid description",
        ):
            self.schema.ingest_schema(self.invalid_schema_category_with_non_string_category_field)

    def test_rejects_schema_that_contains_non_description_leaf(self):
        with raises(
            LabelingSchemaError,
            match="'key' is a leaf but not a description",
        ):
            self.schema.ingest_schema(self.invalid_schema_category_with_non_description_leaf)

    def test_rejects_schema_with_duplicate_label_in_same_category(self):
        with raises(
            LabelingSchemaError,
            match="Category 'reporter' contains label 'windows' more than once",
        ):
            self.schema.ingest_schema(self.invalid_schema_with_duplicate_label_in_same_category)

    def test_top_level_entries_must_not_have_description(self):
        with raises(
            LabelingSchemaError,
            match="Category 'invalid' must not have a description field",
        ):
            self.schema.ingest_schema(self.invalid_schema_with_description_in_top_level)

    def test_does_not_accept_labels_not_in_schema(self):
        self.schema.ingest_schema(self.minimal_schema)
        for invalid_section in ["undefined in schema", "object", "actor"]:
            with raises(KeyDoesnotExistInSchemaError, match="Invalid key '.*'"):
                self.schema.validate_labels({invalid_section: ["windows"]})

        for invalid_label in ["not a defined label", "linux", "macos"]:
            with raises(
                ValueDoesnotExistInSchemaError, match="Invalid value '.*' for key 'reporter'"
            ):
                self.schema.validate_labels({"reporter": [invalid_label]})

    def test_accepts_label_in_schema(self):
        self.schema.ingest_schema(self.minimal_schema)
        assert self.schema.validate_labels({"reporter": ["windows"]})

    def test_toplevel_entry_REFERENCES_does_not_show_up_in_schema(self):
        schema = deepcopy(self.minimal_schema)
        schema["REFERENCES"] = {
            "category": 'This "category" may be used for storing reference objects',
            "key": {
                "description": "This should not be a valid label without being referenced elsewhere."
            },
        }

        self.schema.ingest_schema(schema)
        with raises(KeyDoesnotExistInSchemaError, match="Invalid key 'REFERENCES'"):
            self.schema.validate_labels({"REFERENCES": ["key"]})

    def test_can_use_json_references_in_json_file_to_simplify_document(self):
        schema = deepcopy(self.minimal_schema)
        schema["REFERENCES"] = {
            "category": 'This "category" may be used for storing reference objects',
            "key": {
                "label": {
                    "description": "This should not be a valid label without being referenced elsewhere."
                }
            },
        }
        schema["reporter"]["irrelevant key"] = {"$ref": "#/REFERENCES/key"}

        with JsonTempFile(schema) as schema_file:
            labeling_schema = LabelingSchema.create_from_file(schema_file)

        assert labeling_schema.validate_labels({"reporter": ["label"]})

    def test_get_parent_labels_fails_when_called_for_non_existing_category(self):
        self.schema.ingest_schema(self.deep_schema)

        with raises(LabelingSchemaError):
            self.schema.get_parent_labels("non-existing category", "test")

    def test_get_parent_labels_fails_when_called_for_label_without_description(self):
        self.schema.ingest_schema(self.deep_schema)

        with raises(LabelingSchemaError):
            self.schema.get_parent_labels("reporter", "unixlike")

    def test_get_parent_labels_returns_all_labels_with_description_up_to_category_root(self):
        self.schema.ingest_schema(self.deep_schema)

        assert self.schema.get_parent_labels("reporter", "operatingsystem") == []
        assert self.schema.get_parent_labels("reporter", "linux") == ["operatingsystem"]
        assert self.schema.get_parent_labels("reporter", "android") == ["operatingsystem", "linux"]

    def test_two_schemas_with_different_contents_are_not_equal(self):
        schema1 = LabelingSchema()
        schema1.ingest_schema(self.minimal_schema)
        schema2 = LabelingSchema()
        schema2.ingest_schema(self.deep_schema)

        assert schema1 != schema2

    def test_two_schema_instances_loaded_from_the_same_file_are_equal(self):
        schema1 = LabelingSchema.create_from_file(path_to_schema)
        schema2 = LabelingSchema.create_from_file(path_to_schema)

        assert schema1 == schema2
