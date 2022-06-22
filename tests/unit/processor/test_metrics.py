# pylint: disable=missing-docstring
# pylint: disable=no-self-use
from typing import List

from attr import define

from logprep.abc.metric import Metric


@define(kw_only=True)
class MockChildMetric(Metric):
    metric_a: int = 0
    metric_b: int = 0
    _private_ignore_metric: int = 0
    _calculated_metric: int = 0

    @property
    def combined_metric(self):
        return self.metric_b + self.metric_a

    @property
    def calculated_metric(self):
        return self._calculated_metric

    @calculated_metric.setter
    def calculated_metric(self, value):
        self._calculated_metric = 2 * value


@define(kw_only=True)
class ParentMockMetric(Metric):
    data: List[MockChildMetric]
    more_data: int = 0


class TestMetric:
    def test_metric_exposes_returns_correct_format(self):
        mock_metric = MockChildMetric(labels={"test": "label"})
        mock_metric.metric_a += 1
        mock_metric.metric_b += 1
        mock_metric.calculated_metric += 2
        exposed_metrics = mock_metric.expose()
        expected_metrics = [
            "logprep_calculated_metric test:label 4",
            "logprep_combined_metric test:label 2",
            "logprep_metric_a test:label 1",
            "logprep_metric_b test:label 1",
        ]
        assert exposed_metrics == expected_metrics

    def test_expose_includes_child_metrics_given_in_lists(self):
        ...

    def test_resets_statistic_sets_everything_to_zero(self):
        ...
