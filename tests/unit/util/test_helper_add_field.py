# pylint: disable=no-self-use
# pylint: disable=missing-docstring
import pytest

from logprep.processor.base.exceptions import FieldExistsWarning
from logprep.util.helper import add_fields_to


class TestHelperAddField:
    def test_add_str_content_as_new_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "field": "content"}
        add_fields_to(document, {"field": "content"})
        assert document == expected_document

    def test_add_str_content_as_completely_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": "content"}}
        add_fields_to(document, {"sub.field": "content"})
        assert document == expected_document

    def test_add_str_content_as_partially_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"other_field": "other_content"}}
        expected_document = {
            "source": {"ip": "8.8.8.8"},
            "sub": {"field": "content", "other_field": "other_content"},
        }

        add_fields_to(document, {"sub.field": "content"})
        assert document == expected_document

    def test_provoke_str_duplicate_in_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}, "field": "exists already"}
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_fields_to(document, {"field": "content"})
        assert document

    def test_provoke_str_duplicate_in_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": "exists already"}}
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_fields_to(document, {"sub.field": "content"})
        assert document

    def test_add_dict_content_as_new_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "field": {"dict": "content"}}
        add_fields_to(document, {"field": {"dict": "content"}})
        assert document == expected_document

    def test_add_dict_content_as_completely_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": {"dict": "content"}}}
        add_fields_to(document, {"sub.field": {"dict": "content"}})
        assert document == expected_document

    def test_add_dict_content_as_partially_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"other_field": "other_content"}}
        expected_document = {
            "source": {"ip": "8.8.8.8"},
            "sub": {"field": {"dict": "content"}, "other_field": "other_content"},
        }
        add_fields_to(document, {"sub.field": {"dict": "content"}})
        assert document == expected_document

    def test_provoke_dict_duplicate_in_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}, "field": {"already_existing": "dict"}}
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_fields_to(document, {"field": {"dict": "content"}})
        assert document

    def test_provoke_dict_duplicate_in_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": {"already_existing": "dict"}}}
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_fields_to(document, {"sub.field": {"dict": "content"}})

    def test_add_field_to_overwrites_output_field_in_root_level(self):
        document = {"some": "field", "output_field": "has already content"}
        add_fields_to(document, {"output_field": {"dict": "content"}}, overwrite_target=True)
        assert document.get("output_field") == {"dict": "content"}

    def test_add_field_to_overwrites_output_field_in_nested_level(self):
        document = {"some": "field", "nested": {"output": {"field": "has already content"}}}
        add_fields_to(document, {"nested.output.field": {"dict": "content"}}, overwrite_target=True)
        assert document.get("nested", {}).get("output", {}).get("field") == {"dict": "content"}

    def test_add_field_to_merges_with_target_when_only_given_a_string(self):
        document = {"some": "field", "some_list": ["with a value"]}
        add_fields_to(document, {"some_list": "new value"}, merge_with_target=True)
        assert document.get("some_list") == ["with a value", "new value"]

    def test_add_field_to_merges_with_target_when_given_a_list(self):
        document = {"some": "field", "some_list": ["with a value"]}
        add_fields_to(document, {"some_list": ["first", "second"]}, merge_with_target=True)
        assert document.get("some_list") == ["with a value", "first", "second"]

    def test_add_field_to_raises_if_list_should_be_extended_and_overwritten_at_the_same_time(self):
        document = {"some": "field", "some_list": ["with a value"]}
        with pytest.raises(ValueError, match=r"Can't merge with and overwrite a target"):
            add_fields_to(
                document,
                {"some_list": ["first", "second"]},
                merge_with_target=True,
                overwrite_target=True,
            )
        assert document

    def test_returns_false_if_dotted_field_value_key_exists(self):
        document = {"user": "Franz"}
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_fields_to(document, {"user.in_list": ["user_inlist"]})
        assert document

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
        add_fields_to(
            testdict, {"key1.key2.key3.key4.key5.list": ["content"]}, merge_with_target=True
        )
        assert testdict == expected

    def test_add_field_to_adds_value_not_as_list(self):
        # checks if a newly added field is added not as list, even when `merge_with_target` is True
        document = {"some": "field"}
        add_fields_to(document, {"new": "list"}, merge_with_target=True)
        assert document.get("new") == "list"
        assert not isinstance(document.get("new"), list)

    def test_add_field_to_adds_multiple_fields(self):
        document = {"some": "field"}
        expected = {
            "some": "field",
            "new": "foo",
            "new2": "bar",
        }
        add_fields_to(document, {"new": "foo", "new2": "bar"})
        assert document == expected

    def test_add_field_too_adds_multiple_fields_and_overwrites_one(self):
        document = {"some": "field", "exists_already": "original content"}
        expected = {
            "some": "field",
            "exists_already": {"updated": "content"},
            "new": "another content",
        }
        new_fields = {"exists_already": {"updated": "content"}, "new": "another content"}
        add_fields_to(document, new_fields, overwrite_target=True)
        assert document == expected

    def test_add_field_too_adds_multiple_fields_and_extends_one(self):
        document = {"some": "field", "exists_already": ["original content"]}
        expected = {
            "some": "field",
            "exists_already": ["original content", "extended content"],
            "new": "another content",
        }
        new_fields = {"exists_already": ["extended content"], "new": "another content"}
        add_fields_to(document, new_fields, merge_with_target=True)
        assert document == expected

    def test_add_field_adds_multiple_fields_and_raises_one_field_exists_warning(self):
        document = {"some": "field", "exists_already": "original content"}
        with pytest.raises(FieldExistsWarning, match=r"could not be written"):
            add_fields_to(document, {"exists_already": "new content", "new": "another content"})
        assert document == {
            "some": "field",
            "exists_already": "original content",
            "new": "another content",
        }

    def test_add_fields_to_merges_existing_dict_with_new_dict(self):
        document = {"some": "field", "existing": {"old": "dict"}}
        expected = {
            "some": "field",
            "existing": {"new": "dict", "old": "dict"},
        }
        add_fields_to(document, {"existing": {"new": "dict"}}, merge_with_target=True)
        assert document == expected

    def test_add_fields_to_converts_element_to_list_when_merge_with_target_is_true(self):
        document = {"existing": "element"}
        expected = {"existing": ["element", "new element"]}
        add_fields_to(document, {"existing": ["new element"]}, merge_with_target=True)
        assert document == expected
