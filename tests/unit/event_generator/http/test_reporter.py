# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import datetime
import os
from collections import Counter
from unittest import mock

import pandas as pd
import yaml
from pandas import DatetimeIndex

from logprep.event_generator.http.reporter import Reporter


class TestReporter:
    def setup_method(self):
        self.target_url = "http://testendpoint"
        self.args = {
            "input_dir": "",
            "batch_size": 10,
            "replace_timestamp": True,
            "repeats": 1,
            "tag": "testdata",
            "report": True,
            "target_url": self.target_url,
            "user": "test-user",
            "password": "pass",
        }
        self.reporter = Reporter(self.args)

    def test__init__creates_experiment_dir(self, tmp_path):
        self.reporter.EXPERIMENT_ROOT_DIR = tmp_path
        assert os.path.isdir(self.reporter.experiment_dir)
        assert datetime.datetime.strptime(
            os.path.basename(self.reporter.experiment_dir), "%Y-%m-%d_%H-%M-%S"
        )
        assert datetime.datetime.strptime(self.reporter.experiment_timestamp, "%Y-%m-%d_%H-%M-%S")
        assert os.path.basename(self.reporter.experiment_dir) == self.reporter.experiment_timestamp

    def test__init__creates_data_placeholder(self):
        assert isinstance(self.reporter.data, pd.DataFrame)
        assert len(self.reporter.data) == 0
        assert self.reporter.run_duration == -1

    def test__init__clears_credentials_and_logger(self):
        assert self.reporter.arguments["password"] == "####"
        assert self.reporter.arguments["user"] == "####"
        assert "logger" not in self.reporter.arguments

    def test__prepare_arguments_for_export__clears_credentials_and_logger(self):
        args = {"something": "a", "password": "123", "user": "123"}
        cleared_args = self.reporter._prepare_arguments_for_export(args)
        expected_args = {"something": "a", "password": "####", "user": "####"}
        assert cleared_args == expected_args

    def test__update__writes_first_row_on_empty_dataframe(self):
        statistics = Counter(
            {"Event 200": 10, "Event 400": 10, "Requests 200": 1, "Requests 400": 1}
        )
        assert len(self.reporter.data) == 0
        self.reporter.update(statistics)
        assert len(self.reporter.data) == 1
        statistics.update({"total_events_send": 20, "total_requests_send": 2})
        expected_dataframe = pd.DataFrame(statistics, index=[0])
        assert isinstance(self.reporter.data.index, DatetimeIndex)
        data = self.reporter.data.reset_index(drop=True)
        assert data.equals(expected_dataframe)

    def test__update__appends_to_existing_dataframe(self):
        statistics = Counter(
            {"Event 200": 10, "Event 400": 10, "Requests 200": 1, "Requests 400": 1}
        )
        assert len(self.reporter.data) == 0
        self.reporter.update(statistics)
        assert len(self.reporter.data) == 1
        self.reporter.update(statistics)
        assert len(self.reporter.data) == 2
        statistics.update({"total_events_send": 20, "total_requests_send": 2})
        expected_dataframe = pd.DataFrame([statistics] * 2, index=[0, 1])
        assert isinstance(self.reporter.data.index, DatetimeIndex)
        data = self.reporter.data.reset_index(drop=True)
        assert data.equals(expected_dataframe)

    def test__write_experiment_results__creates_a_report_on_disk__as_smoke_test(self, tmp_path):
        self.reporter.EXPERIMENT_ROOT_DIR = tmp_path
        statistics = Counter(
            {
                "Event 200": 10,
                "Event 400": 10,
                "Requests 200": 1,
                "Requests 400": 1,
                "Batch send time": 0.2,
            }
        )
        # mock time to prevent a flipping test. If the time datapoints jump from one second the
        # next then the calculation for the "per second" metrics won't be as expected/accurate.
        with mock.patch("logprep.event_generator.http.reporter.datetime") as mock_now:
            for i in range(10):
                mock_now.datetime.now.return_value = datetime.datetime(
                    year=2024, month=1, day=31, hour=9, minute=29, second=42, microsecond=i
                )
                self.reporter.update(statistics)
        self.reporter.set_run_duration(2)
        self.reporter.write_experiment_results()

        expected_mean_per_second = pd.DataFrame(
            [10, 10, 200, 20],
            index=["requests_200", "requests_400", "total_events_send", "total_requests_send"],
        )
        expected_metric_sums = pd.DataFrame(
            [10, 10, 200, 20],
            index=["requests_200", "requests_400", "total_events_send", "total_requests_send"],
            columns=["sum"],
        )
        expected_report = self.reporter.REPORT_TEMPLATE.safe_substitute(
            timestamp=self.reporter.experiment_timestamp,
            arguments=yaml.dump(self.reporter.arguments),
            mean_per_second=expected_mean_per_second.to_markdown(),
            totals=expected_metric_sums.to_markdown(),
            mean_batch_send_time="0.20000 s",
            run_duration="2.00000 s",
        )
        with open(self.reporter.experiment_dir / "report.md", "r", encoding="utf8") as file:
            written_report = file.read()
        assert written_report == expected_report
