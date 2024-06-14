"""module for general event handling."""

from typing import Dict, List

from attrs import define, field, validators

from logprep.filter.expression.filter_expression import KeyDoesNotExistError
from logprep.filter.lucene_filter import LuceneFilter
from logprep.util.configuration import yaml
from logprep.util.helper import get_dotted_field_value


def convert_to_documents(data: bytes | list) -> List[Dict]:
    if isinstance(data, bytes):
        data = yaml.load_all(data)
    return [
        Document(manifest_dict) if isinstance(manifest_dict, dict) else manifest_dict
        for manifest_dict in data
        if manifest_dict
    ]


@define
class Documents:

    _documents: List["Document"] = field(
        validator=validators.instance_of(list), converter=convert_to_documents
    )

    def by_query(self, query: str) -> "Documents":
        return Documents([manifest for manifest in self._documents if manifest.query(query)])

    def __len__(self):
        return len(self._documents)

    def __iter__(self):
        return iter(self._documents)


@define
class Document:

    _document: Dict = field(validator=validators.instance_of(dict))

    def query(self, query: str) -> bool:
        filter_expression = LuceneFilter.create(query)
        try:
            return filter_expression.does_match(self._document)
        except KeyDoesNotExistError:
            return False

    def __getitem__(self, key):
        return get_dotted_field_value(self._document, key)

    def __contains__(self, key):
        return self.query(key)
