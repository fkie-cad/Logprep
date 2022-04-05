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
