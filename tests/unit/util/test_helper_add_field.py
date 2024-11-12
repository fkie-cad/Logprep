# pylint: disable=no-self-use
# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.util.helper import add_field_to


class TestHelperAddField:
    def test_add_str_content_as_new_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "field": "content"}
        add_field_to(document, "field", "content")
        assert document == expected_document

    def test_add_str_content_as_completely_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": "content"}}
        add_field_to(document, "sub.field", "content")
        assert document == expected_document

    def test_add_str_content_as_partially_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"other_field": "other_content"}}
        expected_document = {
            "source": {"ip": "8.8.8.8"},
            "sub": {"field": "content", "other_field": "other_content"},
        }

        add_field_to(document, "sub.field", "content")
        assert document == expected_document

    def test_provoke_str_duplicate_in_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}, "field": "exists already"}
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_field_to(document, "field", "content")

    def test_provoke_str_duplicate_in_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": "exists already"}}
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_field_to(document, "sub.field", "content")

    def test_add_dict_content_as_new_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "field": {"dict": "content"}}
        add_field_to(document, "field", {"dict": "content"})
        assert document == expected_document

    def test_add_dict_content_as_completely_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": {"dict": "content"}}}
        add_field_to(document, "sub.field", {"dict": "content"})
        assert document == expected_document

    def test_add_dict_content_as_partially_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"other_field": "other_content"}}
        expected_document = {
            "source": {"ip": "8.8.8.8"},
            "sub": {"field": {"dict": "content"}, "other_field": "other_content"},
        }
        add_field_to(document, "sub.field", {"dict": "content"})
        assert document == expected_document

    def test_provoke_dict_duplicate_in_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}, "field": {"already_existing": "dict"}}
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_field_to(document, "field", {"dict": "content"})

    def test_provoke_dict_duplicate_in_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": {"already_existing": "dict"}}}
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_field_to(document, "sub.field", {"dict": "content"})

    def test_add_field_to_overwrites_output_field_in_root_level(self):
        document = {"some": "field", "output_field": "has already content"}
        add_field_to(document, "output_field", {"dict": "content"}, overwrite_target_field=True)
        assert document.get("output_field") == {"dict": "content"}

    def test_add_field_to_overwrites_output_field_in_nested_level(self):
        document = {"some": "field", "nested": {"output": {"field": "has already content"}}}
        add_field_to(
            document, "nested.output.field", {"dict": "content"}, overwrite_target_field=True
        )
        assert document.get("nested", {}).get("output", {}).get("field") == {"dict": "content"}

    def test_add_field_to_extends_list_when_only_given_a_string(self):
        document = {"some": "field", "some_list": ["with a value"]}
        add_field_to(document, "some_list", "new value", extends_lists=True)
        assert document.get("some_list") == ["with a value", "new value"]

    def test_add_field_to_extends_list_when_given_a_list(self):
        document = {"some": "field", "some_list": ["with a value"]}
        add_field_to(document, "some_list", ["first", "second"], extends_lists=True)
        assert document.get("some_list") == ["with a value", "first", "second"]

    def test_add_field_to_raises_if_list_should_be_extended_and_overwritten_at_the_same_time(self):
        document = {"some": "field", "some_list": ["with a value"]}
        with pytest.raises(ValueError, match=r"can't be overwritten and extended at the same time"):
            add_field_to(
                document,
                "some_list",
                ["first", "second"],
                extends_lists=True,
                overwrite_target_field=True,
            )

    def test_returns_false_if_dotted_field_value_key_exists(self):
        document = {"user": "Franz"}
        content = ["user_inlist"]
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_field_to(document, "user.in_list", content)

    def test_add_list_with_nested_keys(self):
        testdict = {
            "key1": {"key2": {"key3": {"key4": {"key5": {"list": ["existing"], "key6": "value"}}}}}
        }
        expected = {
            "key1": {
                "key2": {
                    "key3": {"key4": {"key5": {"list": ["existing", "content"], "key6": "value"}}}
                }
            }
        }
        add_field_to(testdict, "key1.key2.key3.key4.key5.list", ["content"], extends_lists=True)
        assert testdict == expected

    def test_add_value_not_as_list_if_it_is_a_new_value_even_though_extends_lists_is_true(self):
        document = {
            "some": "field",
        }
        add_field_to(document, "new", "list", extends_lists=True)
        assert document.get("new") == "list"
