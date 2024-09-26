# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=attribute-defined-outside-init
import pytest

from logprep.util.event import Document, Documents, convert_to_documents


class TestConvertToDocuments:

    @pytest.mark.parametrize(
        "data, expected_count",
        [
            (b"---\nkey: value", 1),
            (b"---\nkey: value\n", 1),
            (b"---\nkey: value\n---\nother_key", 2),
        ],
    )
    def test_convert_to_documents_returns_documents_count(self, data, expected_count):
        documents = convert_to_documents(data)
        assert documents
        assert len(documents) == expected_count
        assert isinstance(documents[0], Document)

    def test_not_valid_yaml_data_raises_exception(self):
        with pytest.raises(TypeError, match="not valid yaml data"):
            convert_to_documents("not valid data")


class TestDocuments:

    def setup_method(self):
        raw_data = b"""---
key: value
other_key: other_value
---
key: value
other_key: different_value
---
version: 1
key:
  nested_key: nested_value
other_key:
  - item1
  - item2
  - item3: item3_value
"""
        self.documents = Documents(raw_data)

    @pytest.mark.parametrize(
        "data",
        [
            b"---\nkey: value\n---\nother_key",
            b"---\nkey: value\n---\nother_key\n",
            "---\nkey: value\n---\nother_key\n",
            {"key": "value"},
            [{"key": "value"}, {"other_key": "other_value"}],
        ],
    )
    def test_documents(self, data):
        assert isinstance(Documents(data), Documents)

    def test_documents_by_query_returns_documents(self):
        documents = self.documents.by_query("key: value")
        assert documents
        assert len(documents) == 2
        assert isinstance(documents[0], Document)

    def test_documents_is_iterable(self):
        for document in self.documents:
            assert isinstance(document, Document)


class TestDocument:

    def test_document(self):
        assert isinstance(Document({"key": "value"}), Document)

    def test_query_returns_boolean(self):
        document = Document({"key": "value"})
        assert document.query("key: value")
        assert not document.query("key: other_value")

    def test_getitem_returns_value(self):
        document = Document({"key": "value"})
        assert document["key"] == "value"
        assert document["other_key"] is None
        assert document["other_key"] == document._document.get("other_key")
        assert document["nested_key"] is None
        assert document["nested_key"] == document._document.get("nested_key")

    def test_getitem_returns_nested_value(self):
        document = Document({"key": {"nested_key": "nested_value"}})
        assert document["key.nested_key"] == "nested_value"
        assert document["key.other_key"] is None

    def test_contains_returns_boolean(self):
        document = Document({"key": "value", "upper_key": {"nested_key": "nested_value"}})
        assert "key" in document
        assert "other_key" not in document
        assert "key: value" in document
        assert "upper_key.nested_key" in document
        assert "upper_key.other_key" not in document
        assert "upper_key.nested_key: nested_value" in document
