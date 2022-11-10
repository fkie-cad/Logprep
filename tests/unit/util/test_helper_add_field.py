# pylint: disable=no-self-use
# pylint: disable=missing-docstring
import pytest

from logprep.util.helper import add_field_to


class TestHelperAddField:
    def test_add_str_content_as_new_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "field": "content"}

        add_was_successful = add_field_to(document, "field", "content")

        assert add_was_successful, "Found duplicate even though there shouldn't be one"
        assert document == expected_document

    def test_add_str_content_as_completely_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": "content"}}

        add_was_successful = add_field_to(document, "sub.field", "content")
        assert add_was_successful, "Found duplicate even though there shouldn't be one"
        assert document == expected_document

    def test_add_str_content_as_partially_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"other_field": "other_content"}}
        expected_document = {
            "source": {"ip": "8.8.8.8"},
            "sub": {"field": "content", "other_field": "other_content"},
        }

        add_was_successful = add_field_to(document, "sub.field", "content")

        assert add_was_successful, "Found duplicate even though there shouldn't be one"
        assert document == expected_document

    def test_provoke_str_duplicate_in_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}, "field": "exists already"}

        add_was_successful = add_field_to(document, "field", "content")

        assert not add_was_successful, "Found no duplicate even though there should be one"

    def test_provoke_str_duplicate_in_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": "exists already"}}

        add_was_successful = add_field_to(document, "sub.field", "content")

        assert not add_was_successful, "Found no duplicate even though there should be one"

    def test_add_dict_content_as_new_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "field": {"dict": "content"}}

        add_was_successful = add_field_to(document, "field", {"dict": "content"})

        assert add_was_successful, "Found duplicate even though there shouldn't be one"
        assert document == expected_document

    def test_add_dict_content_as_completely_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}}
        expected_document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": {"dict": "content"}}}

        add_was_successful = add_field_to(document, "sub.field", {"dict": "content"})

        assert add_was_successful, "Found duplicate even though there shouldn't be one"
        assert document == expected_document

    def test_add_dict_content_as_partially_new_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"other_field": "other_content"}}
        expected_document = {
            "source": {"ip": "8.8.8.8"},
            "sub": {"field": {"dict": "content"}, "other_field": "other_content"},
        }

        add_was_successful = add_field_to(document, "sub.field", {"dict": "content"})

        assert add_was_successful, "Found duplicate even though there shouldn't be one"
        assert document == expected_document

    def test_provoke_dict_duplicate_in_root_field(self):
        document = {"source": {"ip": "8.8.8.8"}, "field": {"already_existing": "dict"}}

        add_was_successful = add_field_to(document, "field", {"dict": "content"})

        assert not add_was_successful, "Found no duplicate even though there should be one"

    def test_provoke_dict_duplicate_in_dotted_subfield(self):
        document = {"source": {"ip": "8.8.8.8"}, "sub": {"field": {"already_existing": "dict"}}}

        add_was_successful = add_field_to(document, "sub.field", {"dict": "content"})

        assert not add_was_successful, "Found no duplicate even though there should be one"

    def test_add_field_to_overwrites_output_field_in_root_level(self):
        document = {"some": "field", "output_field": "has already content"}

        add_was_successful = add_field_to(
            document, "output_field", {"dict": "content"}, overwrite_output_field=True
        )

        assert add_was_successful, "Output field was overwritten"
        assert document.get("output_field") == {"dict": "content"}

    def test_add_field_to_overwrites_output_field_in_nested_level(self):
        document = {"some": "field", "nested": {"output": {"field": "has already content"}}}

        add_was_successful = add_field_to(
            document, "nested.output.field", {"dict": "content"}, overwrite_output_field=True
        )

        assert add_was_successful, "Output field was overwritten"
        assert document.get("nested", {}).get("output", {}).get("field") == {"dict": "content"}

    def test_add_field_to_extends_list_when_only_given_a_string(self):
        document = {"some": "field", "some_list": ["with a value"]}

        add_was_successful = add_field_to(document, "some_list", "new value", extends_lists=True)

        assert add_was_successful, "Output field was overwritten"
        assert document.get("some_list") == ["with a value", "new value"]

    def test_add_field_to_extends_list_when_given_a_list(self):
        document = {"some": "field", "some_list": ["with a value"]}

        add_was_successful = add_field_to(
            document, "some_list", ["first", "second"], extends_lists=True
        )

        assert add_was_successful, "Output field was overwritten"
        assert document.get("some_list") == ["with a value", "first", "second"]

    def test_add_field_to_raises_if_list_should_be_extended_and_overwritten_at_the_same_time(self):
        document = {"some": "field", "some_list": ["with a value"]}

        with pytest.raises(
            AssertionError,
            match=r"An output field can't be overwritten and " r"extended at the same time",
        ):
            _ = add_field_to(
                document,
                "some_list",
                ["first", "second"],
                extends_lists=True,
                overwrite_output_field=True,
            )

    def test_returns_false_if_dotted_field_value_key_exists(self):
        document = {"user": "Franz"}
        content = ["user_inlist"]
        add_was_successful = add_field_to(document, "user.in_list", content)
        assert not add_was_successful

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
        add_was_successful = add_field_to(
            testdict, "key1.key2.key3.key4.key5.list", ["content"], extends_lists=True
        )
        assert add_was_successful
        assert testdict == expected
