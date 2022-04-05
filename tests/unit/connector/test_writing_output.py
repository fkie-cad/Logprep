from os import remove
from os.path import isfile
from json import dumps

import pytest

from logprep.output.writing_output import WritingOutput

OUTPUT_PATH = "tests/testdata/acceptance/test_kafka_data_processing_acceptance.out"
OUTPUT_PATH_CUSTOM = "tests/testdata/test_kafka_data_processing_acceptance_custom.out"


@pytest.fixture
def output():
    _remove_file_if_exists(OUTPUT_PATH)
    yield WritingOutput(OUTPUT_PATH)
    _remove_file_if_exists(OUTPUT_PATH)


@pytest.fixture
def output_custom():
    _remove_file_if_exists(OUTPUT_PATH)
    _remove_file_if_exists(OUTPUT_PATH_CUSTOM)
    yield WritingOutput(OUTPUT_PATH, output_path_custom=OUTPUT_PATH_CUSTOM)
    _remove_file_if_exists(OUTPUT_PATH_CUSTOM)
    _remove_file_if_exists(OUTPUT_PATH)


@pytest.fixture(scope="session")
def document():
    return {"the": "document"}


def _remove_file_if_exists(test_output_path):
    try:
        remove(test_output_path)
    except FileNotFoundError:
        pass


class TestWritingOutput:
    def test_describe_endpoint(self, output, document):
        assert output.describe_endpoint() == "writer"

    def test_store_appends_document_to_variable(self, output, document):
        output.store(document)

        assert len(output.events) == 1
        assert output.events[0] == document

    def test_store_custom_appends_document_to_variable(self, output_custom, document):
        output_custom.store_custom(document, target="whatever")

        assert len(output_custom.events) == 1
        assert output_custom.events[0] == document

    def test_store_maintains_order_of_documents(self, output):
        for i in range(0, 3):
            output.store({"order": i})

        assert len(output.events) == 3
        for order in range(0, 3):
            assert output.events[order]["order"] == order

    def test_stores_failed_events_in_respective_list(self, output):
        output.store_failed("message", {"doc": "received"}, {"doc": "processed"})

        assert len(output.failed_events) == 1
        assert output.failed_events[0] == ("message", {"doc": "received"}, {"doc": "processed"})

    def test_write_document_to_file_on_store(self, output, document):
        output.store(document)
        output.shut_down()
        assert isfile(OUTPUT_PATH)

        with open(OUTPUT_PATH, "r") as output_file:
            assert output_file.readline().strip() == dumps(document)
            assert output_file.readline().strip() == ""

    def test_write_document_to_file_on_store_custom(self, output_custom, document):
        output_custom.store_custom(document, target="whatever")
        output_custom.shut_down()
        assert isfile(OUTPUT_PATH_CUSTOM)

        with open(OUTPUT_PATH_CUSTOM, "r") as output_file2:
            assert output_file2.readline().strip() == dumps(document)
            assert output_file2.readline().strip() == ""

    def test_write_multiple_documents_to_file_on_store(self, output, document):
        output.store(document)
        output.store(document)
        output.shut_down()
        assert isfile(OUTPUT_PATH)

        with open(OUTPUT_PATH, "r") as output_file:
            assert output_file.readline().strip() == dumps(document)
            assert output_file.readline().strip() == dumps(document)
            assert output_file.readline().strip() == ""
