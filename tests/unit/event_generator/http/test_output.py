# pylint: disable=missing-docstring
import pytest
import responses

from logprep.event_generator.http.output import Output

TARGET_URL = "https://www.test.de"


@pytest.fixture(name="output")
def get_output():
    config = {"target_url": TARGET_URL, "user": "user", "password": "password"}
    return Output(config=config)


class TestOutput:
    @responses.activate
    def test_one_repeat(self, output):
        responses.add(responses.POST, f"{TARGET_URL}/123", status=200)
        events_string = """[{"event1_key": "event1_value"}\n{"event2_key": "event2_value"}]"""
        batch = (f"{TARGET_URL}/123", events_string)
        statistics = output.send(batch)
        assert isinstance(statistics.get("Batch send time"), float)
        assert statistics.get("Batch send time") > 0
        del statistics["Batch send time"]  # to simplify next assertion
        expected_statistics = {
            f"Requests http status {str(200)}": 1,
            f"Events http status {str(200)}": len(events_string.splitlines()),
        }
        assert statistics == expected_statistics

    @responses.activate
    def test_404_status_code(self, output):
        responses.add(responses.POST, f"{TARGET_URL}/123", status=404)
        events_string = """[{"event1_key": "event1_value"}\n{"event2_key": "event2_value"}]"""
        batch = (f"{TARGET_URL}/123", events_string)
        statistics = output.send(batch)
        assert isinstance(statistics.get("Batch send time"), float)
        assert statistics.get("Batch send time") > 0
        del statistics["Batch send time"]  # to simplify next assertion
        expected_statistics = {
            f"Requests http status {str(404)}": 1,
            f"Events http status {str(404)}": len(events_string.splitlines()),
        }
        assert statistics == expected_statistics
