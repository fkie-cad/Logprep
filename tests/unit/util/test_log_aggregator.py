# pylint: disable=missing-docstring
# pylint: disable=protected-access
from logging import makeLogRecord
from random import randint
from unittest import mock

import pytest

from logprep.util.log_aggregator import Aggregator


@pytest.fixture(autouse=True)
def clear_aggregator():
    yield
    Aggregator.logs.clear()


class TestAggregator:
    def test_initialized(self):
        Aggregator.setup(5, 6)
        assert Aggregator.count_threshold == 5
        assert Aggregator.log_period == 6
        assert len(Aggregator.logs) == 0

    def test_one_log_without_aggregation(self):
        Aggregator._aggregate(makeLogRecord({"msg": "Test log"}))
        assert len(Aggregator.logs) == 1
        self.assert_count(1)

    def test_one_log_many_times_without_aggregation(self):
        log_cnt = 10
        for _ in range(log_cnt):
            Aggregator._aggregate(makeLogRecord({"msg": "Test log"}))
        assert len(Aggregator.logs) == 1
        self.assert_count(log_cnt)

    def test_many_logs_many_times_without_aggregation(self):
        log_cnt = 10
        for _ in range(log_cnt):
            Aggregator._aggregate(makeLogRecord({"msg": "Test log 1"}))
            Aggregator._aggregate(makeLogRecord({"msg": "Test log 2"}))
        assert len(Aggregator.logs) == 2
        self.assert_count(log_cnt)

    @mock.patch("logprep.util.log_aggregator.time", return_value=0.0)
    def test_aggregation_no_new_aggregation_after_period_if_no_new_logs_at_print(self, mock_time):
        cnt_threshold = 3
        period = 0.25
        Aggregator.setup(cnt_threshold, period)
        log_cnt = 10

        should_print = self.add_log_n_times(log_cnt)
        assert should_print == [True] * cnt_threshold + [False] * (log_cnt - cnt_threshold)
        assert len(Aggregator.logs) == 1

        for log in Aggregator.logs.values():
            assert log["cnt_passed"] == cnt_threshold
            assert log["cnt"] == 10
            assert log["first_record"].msg == "Test log"
            assert log["last_record"].msg == "Test log"

        Aggregator._perform_logging_if_possible()

        for log in Aggregator.logs.values():
            assert log["cnt_passed"] == 0
            assert log["cnt"] == 0
            assert log["first_record"].msg == f"Test log ({log_cnt - cnt_threshold} in ~0.0 sek)"
            assert log["last_record"] is None
            assert log["aggregate"] is True

        mock_time.return_value = mock_time.return_value + period + 0.05
        Aggregator._perform_logging_if_possible()

        for log in Aggregator.logs.values():
            assert log["aggregate"] is False

    @mock.patch("logprep.util.log_aggregator.time", return_value=0.0)
    def test_aggregation_converts_to_minutes(self, mock_time):
        cnt_threshold = 3
        period = 300
        Aggregator.setup(cnt_threshold, period)
        log_cnt = 10

        should_print = self.add_log_n_times(log_cnt)
        assert should_print == [True] * cnt_threshold + [False] * (log_cnt - cnt_threshold)
        assert len(Aggregator.logs) == 1

        for log in Aggregator.logs.values():
            assert log["cnt_passed"] == cnt_threshold
            assert log["cnt"] == 10
            assert log["first_record"].msg == "Test log"
            assert log["last_record"].msg == "Test log"

        mock_time.return_value = mock_time.return_value + 61

        Aggregator._perform_logging_if_possible()

        for log in Aggregator.logs.values():
            assert log["cnt_passed"] == 0
            assert log["cnt"] == 0
            assert log["first_record"].msg == f"Test log ({log_cnt - cnt_threshold} in ~1.0 min)"
            assert log["last_record"] is None
            assert log["aggregate"] is True

    @mock.patch("logprep.util.log_aggregator.time", return_value=0.0)
    @mock.patch("logging.getLogger")
    def test_aggregation_keep_aggregating_on_consecutive_periods(
        self, logging_get_logger, mock_time
    ):
        cnt_threshold = 3
        period = 0.25
        Aggregator.setup(cnt_threshold, period)
        log_cnt = 10

        # It should log the first cnt_threshold logs normally
        should_print = self.add_log_n_times(log_cnt)
        assert should_print == [True] * cnt_threshold + [False] * (log_cnt - cnt_threshold)
        assert len(Aggregator.logs) == 1

        for log in Aggregator.logs.values():
            assert log["cnt_passed"] == cnt_threshold
            assert log["cnt"] == 10
            assert log["first_record"].msg == "Test log"
            assert log["last_record"].msg == "Test log"

        Aggregator._perform_logging_if_possible()

        for log in Aggregator.logs.values():
            assert log["cnt_passed"] == 0
            assert log["cnt"] == 0
            assert log["first_record"].msg == f"Test log ({log_cnt - cnt_threshold} in ~0.0 sek)"
            assert log["last_record"] is None
            assert log["aggregate"] is True

        # It should only print aggregated if there were still too many logs after
        # the last aggregation unless the next period passed
        additional_aggregation_cnt = 3
        for _ in range(additional_aggregation_cnt):
            mock_time.return_value = mock_time.return_value + period + 0.05
            random_log_cnt = log_cnt + randint(1, 10)
            should_print = self.add_log_n_times(random_log_cnt)
            assert should_print == [False] * random_log_cnt

            self.assert_count(random_log_cnt)

            Aggregator._perform_logging_if_possible()

            for log in Aggregator.logs.values():
                assert log["cnt_passed"] == 0
                assert log["cnt"] == 0
                assert log["first_record"].msg == f"Test log ({random_log_cnt} in ~{period} sek)"
                assert log["last_record"] is None
                assert log["aggregate"] is True

        assert logging_get_logger.call_count == additional_aggregation_cnt + 1

    @staticmethod
    def add_log_n_times(log_cnt):
        should_print = []
        for _ in range(log_cnt):
            should_print.append(
                Aggregator().filter(
                    makeLogRecord({"msg": "Test log", "levelno": 20, "created": 0.0})
                )
            )
        return should_print

    @staticmethod
    def assert_count(log_cnt):
        for log in Aggregator.logs.values():
            assert log["cnt"] == log_cnt
