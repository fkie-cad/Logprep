# pylint: disable=missing-docstring
from logging import getLogger
from unittest import mock
import pytest
from logprep.processor.selective_extractor.factory import SelectiveExtractorFactory
from logprep.processor.selective_extractor.processor import SelectiveExtractorConfigurationError

logger = getLogger()

read_data = "message"
mock_open = mock.mock_open(read_data=read_data)


@pytest.fixture()
def selective_extractor():
    config = {
        "type": "selective_extractor",
        "selective_extractor_topic": "test_topic",
        "extractor_list": "tests/testdata/unit/selective_extractor/test_extraction_list.txt",
    }
    with mock.patch("builtins.open", mock_open):
        selective_extractor = SelectiveExtractorFactory.create(
            "test-selective-extractor", config, logger
        )
        return selective_extractor


class TestSelectiveExtractor:
    def test_selective_extractor_does_not_change_orig_doc(self, selective_extractor):
        assert selective_extractor.ps.processed_count == 0
        document = {"user": "test_user", "other": "field"}
        exp_document = {"user": "test_user", "other": "field"}

        selective_extractor.process(document)

        assert document == exp_document

    def test_selective_extractor_events_processed_count(self, selective_extractor):
        assert selective_extractor.ps.processed_count == 0
        document = {"user": "test_user", "other": "field"}

        selective_extractor.process(document)

        assert selective_extractor.ps.processed_count == 1

    def test_selective_extractor_self_describe(self, selective_extractor):
        assert selective_extractor.describe() == "Selective Extractor (test-selective-extractor)"

    def test_invalid_extraction_list(self):
        config = {
            "type": "selective_extractor",
            "selective_extractor_topic": "test_topic",
            "extractor_list": "tests/testdata/unit/selective_extractor/invalid_test.txt",
        }
        with pytest.raises(
            SelectiveExtractorConfigurationError,
            match=r"Selective Extractor \(test-selective-extractor\)\: "
            r"The given extraction_list file does not exist or is not a valid '\.txt' file\.",
        ):
            _ = SelectiveExtractorFactory.create("test-selective-extractor", config, logger)

    def test_extractor_list_is_loaded_from_file(self, selective_extractor):
        assert "message" in selective_extractor.extraction_fields

    def test_process_returns_tuple_with_found_extraction_field(self, selective_extractor):
        document = {"message": "test_message", "other": "field"}
        result = selective_extractor.process(document)
        assert isinstance(result, tuple)

    def test_process_returns_selective_extractor_topic(self, selective_extractor):
        document = {"message": "test_message", "other": "field"}
        result = selective_extractor.process(document)
        assert result[1] == "test_topic"

    def test_process_returns_extracted_fields(self, selective_extractor):
        document = {"message": "test_message", "other": "field"}
        result = selective_extractor.process(document)
        assert result[0] == [{"message": "test_message"}]

    def test_process_returns_none_without_extraction_field(self, selective_extractor):
        document = {"nomessage": "test_message", "other": "field"}
        result = selective_extractor.process(document)
        assert result is None
