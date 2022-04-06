"""This module is used create labeling schemas."""

from typing import Optional, List, Any

from json import JSONDecodeError

from jsonref import load

from logprep.processor.base.exceptions import (
    ValueDoesnotExistInSchemaError,
    KeyDoesnotExistInSchemaError,
)


class LabelingSchemaError(BaseException):
    """Base class for LabelingSchema related exceptions."""


class InvalidLabelingSchemaFileError(LabelingSchemaError):
    """Raise if labeling schema file is invalid."""

    def __init__(self, path: Optional[str] = None, message: Optional[str] = None):
        if (path is not None) and (message is not None):
            super().__init__(f'Not a valid schema file: {message}: "{path}".')
        elif message is not None:
            super().__init__(f"Not a valid schema file: {message}.")
        elif path is not None:
            super().__init__(f'Not a valid schema file: "{path}".')
        else:
            super().__init__("Not a valid schema file.")


class SchemaFileNotFoundError(InvalidLabelingSchemaFileError):
    """Raise if labeling schema file could not be found."""

    def __init__(self, path: str):
        super().__init__(f'Not a valid schema file: "{path}".')


class InvalidLabelTreeError(LabelingSchemaError):
    """Raise if schema definition is invalid."""

    def __init__(self, message: Optional[str] = None):
        if message is None:
            super().__init__("Invalid schema definition")
        else:
            super().__init__(f"Invalid schema definition: {message}")


class CategoryWithoutDesciptionInSchemaError(InvalidLabelTreeError):
    """Raise if category does not have a vailid description."""

    def __init__(self, name: str):
        super().__init__(f'Category "{name}" does not have a valid description')


class CategoryMustNotContainDescriptionFieldError(InvalidLabelTreeError):
    """Raise if category has a description field."""

    def __init__(self, name: str):
        super().__init__(f'Category "{name}" must not have a description field')


class NonDescriptionLeafError(InvalidLabelTreeError):
    """Raise if leaf has no description field."""

    def __init__(self, name: str):
        super().__init__(f'"{name}" is a leaf but not a description')


class DuplicateLabelInCategoryError(InvalidLabelTreeError):
    """Raise if category contains duplicate labels."""

    def __init__(self, category: str, label: str):
        super().__init__(f'Category "{category}" contains label "{label}" more than once')


class LabelWithoutDesciptionInSchemaError(InvalidLabelTreeError):
    """Raise if label has no valid description."""

    def __init__(self, name: str):
        super().__init__(f'Label "{name}" does not have a valid description')


class NoSuchCategoryError(LabelingSchemaError):
    """Raise if a category does not exist."""


class CannotRetrieveParentsForLabelWithoutDescriptionError(LabelingSchemaError):
    """Raise if retrieval of parents on label without description is attempted."""


class LabelingSchema:
    """Schema used for labeling."""

    def __init__(self):
        self._schema = {}
        self._parents = {}

    def __eq__(self, other: "LabelingSchema") -> bool:
        return self._schema == other.schema

    @property
    def schema(self) -> dict:
        # pylint: disable=C0111
        return self._schema

    @staticmethod
    def create_from_file(path: str) -> "LabelingSchema":
        """Create a schema from a file at a given path."""
        try:
            with open(path, "r") as file:
                schema = load(file)
            if not schema:
                raise InvalidLabelingSchemaFileError(path)
            labeling_schema = LabelingSchema()
            labeling_schema.ingest_schema(schema)
            return labeling_schema
        except FileNotFoundError as error:
            raise InvalidLabelingSchemaFileError(path=path, message="File not found") from error
        except OSError as error:
            raise InvalidLabelingSchemaFileError(message=str(error)) from error
        except JSONDecodeError as error:
            raise InvalidLabelingSchemaFileError(
                path=path, message="JSON decoder error: " + str(error)
            ) from error
        except InvalidLabelTreeError as error:
            raise InvalidLabelingSchemaFileError(path=path, message=str(error)) from error

    def ingest_schema(self, schema: dict):
        """Verify schema and extract labels and parent labels per category."""
        self._schema = {}
        for key in schema:
            if key == "REFERENCES":
                continue

            self._verify_category(key, schema[key])
            category = dict(schema[key])
            del category["category"]  # get rid of the implied corner cases

            self._schema[key] = self._extract_labels(category, 1)
            self._parents[key] = self._extract_parents([], category)
            self._fail_if_category_contains_duplicate_labels(key)

    def _verify_category(self, name: str, category: dict):
        if not (("category" in category) and isinstance(category["category"], str)):
            raise CategoryWithoutDesciptionInSchemaError(name)
        if "description" in category and isinstance(category["description"], str):
            raise CategoryMustNotContainDescriptionFieldError(name)

        for key in category:
            if key == "category":
                continue
            self._verify_label_tree(key, category[key])

    def _verify_label_tree(self, name: str, label_tree: dict):
        if not isinstance(label_tree, dict):
            raise InvalidLabelTreeError
        if not label_tree:
            raise InvalidLabelTreeError

        for key in label_tree:
            if key == "description":
                if self._is_description(key, label_tree[key]):
                    continue
                raise LabelWithoutDesciptionInSchemaError(name)
            if not isinstance(label_tree[key], dict):
                raise NonDescriptionLeafError(key)
            self._verify_label_tree(key, label_tree[key])

    def _extract_labels(self, document: dict, depth: int) -> List[str]:
        labels = []

        for key in document:
            if (key == "description") and isinstance(document[key], str):
                continue
            if isinstance(document[key], dict):
                if self._has_description(document[key]):
                    labels.append(key)
                labels += self._extract_labels(document[key], depth + 1)

        return labels

    def _fail_if_category_contains_duplicate_labels(self, name: str):
        if len(set(self._schema[name])) < len(self._schema[name]):
            for label in self._schema[name]:
                if self._schema[name].count(label) > 1:
                    raise DuplicateLabelInCategoryError(name, label)

    def _has_description(self, document: dict) -> bool:
        if "description" in document:
            return self._is_description("description", document["description"])
        return False

    @staticmethod
    def _is_description(key: str, value: Any):
        if (key == "description") and isinstance(value, str):
            return True
        return False

    def _extract_parents(self, parents: list, label_tree: dict) -> dict:
        new_parents = {}

        for key in label_tree:
            if self._is_description(key, label_tree[key]):
                continue

            current_parents = list(parents)
            if self._has_description(label_tree[key]):
                new_parents[key] = parents
                current_parents.append(key)
            new_parents.update(self._extract_parents(current_parents, label_tree[key]))
        return new_parents

    def validate_labels(self, labels: dict) -> bool:
        """Check if labels are valid according to schema."""
        for key in labels:
            if key not in self._schema:
                raise KeyDoesnotExistInSchemaError(key)
            for label in labels[key]:
                if label not in self._schema[key]:
                    raise ValueDoesnotExistInSchemaError(key, label)
        return True

    def get_parent_labels(self, category: str, label: str):
        """Get parent labels of a given label and category."""
        if category not in self._parents:
            raise NoSuchCategoryError
        if label not in self._parents[category]:
            raise CannotRetrieveParentsForLabelWithoutDescriptionError
        return self._parents[category][label]
