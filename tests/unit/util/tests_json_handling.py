# pylint: disable=missing-docstring
# pylint: disable=no-self-use
import json
import os
from json import JSONDecodeError

import pytest

from logprep.util.json_handling import parse_json


class TestJsonHandling:
    def test_parse_json_returns_single_json_as_list_from_single_file(self, tmp_path):
        test_json = {"this is a": "test json"}
        test_file_path = os.path.join(tmp_path, "test.json")
        with open(test_file_path, "w", encoding="utf8") as file:
            json.dump(test_json, file)
        parsed_json = parse_json(test_file_path)
        assert parsed_json == [test_json]

    def test_parse_json_returns_list_of_jsons_from_single_file(self, tmp_path):
        test_jsons = [{"this is a": "test json"}, {"this is a": "second test json"}]
        test_file_path = os.path.join(tmp_path, "test.json")
        with open(test_file_path, "w", encoding="utf8") as file:
            json.dump(test_jsons, file)
        parsed_json = parse_json(test_file_path)
        assert parsed_json == test_jsons

    def test_parse_json_raises_json_decode_error_on_invalid_json_format(self, tmp_path):
        test_jsons = '{"this is a": "broken test json with a missing curly bracket"\n'
        test_file_path = os.path.join(tmp_path, "test.json")
        with open(test_file_path, "w", encoding="utf8") as file:
            file.writelines(test_jsons)
        with pytest.raises(
            JSONDecodeError, match=r"Expecting ',' delimiter: line 2 column 1 \(char 62\)"
        ):
            _ = parse_json(test_file_path)
