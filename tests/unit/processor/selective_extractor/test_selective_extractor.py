from logging import getLogger

import pytest

from logprep.processor.selective_extractor.processor import SelectiveExtractorConfigurationError

pytest.importorskip('logprep.processor.selective_extractor')

from logprep.processor.selective_extractor.factory import SelectiveExtractorFactory

logger = getLogger()


@pytest.fixture()
def selective_extractor():
    config = {
        'type': 'selective_extractor',
        'selective_extractor_topic': 'test_topic',
        'extractor_list': 'tests/testdata/unit/selective_extractor/test_extraction_list.txt'
    }

    selective_extractor = SelectiveExtractorFactory.create('test-selective-extractor', config, logger)
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
        assert selective_extractor.describe() == 'Selective Extractor (test-selective-extractor)'

    def test_invalid_extraction_list(self):
        config = {
            'type': 'selective_extractor',
            'selective_extractor_topic': 'test_topic',
            'extractor_list': 'tests/testdata/unit/selective_extractor/invalid_test.txt'
        }
        with pytest.raises(SelectiveExtractorConfigurationError,
                           match=r"Selective Extractor \(test-selective-extractor\)\: "
                                 r"The given extraction_list file does not exist or is not a valid '\.txt' file\."):
            _ = SelectiveExtractorFactory.create('test-selective-extractor', config, logger)
