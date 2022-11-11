# pylint: disable=missing-docstring
# pylint: disable=no-self-use
from typing import List

import numpy as np
from attr import define

from logprep.metrics.metric import Metric, calculate_new_average, get_settable_metrics


@define(kw_only=True)
class MockChildMetric(Metric):
    metric_a: int = 0
    metric_b: float = 0.0
    _calculated_metric: int = 0
    _private_ignore_metric: int = 0

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
class MockParentMetric(Metric):
    data: List[MockChildMetric]
    direct_non_list_metric: MockChildMetric
    more_data: int = 0


class TestMetric:
    def test_metric_exposes_returns_correct_format(self):
        mock_metric = MockChildMetric(labels={"test": "label"})
        mock_metric.metric_a += 1
        mock_metric.metric_b += 1
        mock_metric.calculated_metric += 2
        exposed_metrics = mock_metric.expose()
        expected_metrics = {
            "logprep_metric_a;test:label": 1,
            "logprep_metric_b;test:label": 1.0,
            "logprep_combined_metric;test:label": 2.0,
            "logprep_calculated_metric;test:label": 4,
        }
        assert exposed_metrics == expected_metrics

    def test_expose_metric_ignores_private_attributes(self):
        mock_metric = MockChildMetric(labels={"test": "label"})
        exposed_metrics = mock_metric.expose()
        private_metric = "_private_ignore_metric"
        assert mock_metric.__getattribute__(private_metric) == 0
        assert private_metric not in " ".join(exposed_metrics)

    def test_expose_includes_child_metrics_given_in_lists(self):
        mock_child_metric = MockChildMetric(labels={"type": "child"})
        mock_child_metric_two = MockChildMetric(labels={"type": "child2"})
        mock_parent_metric = MockParentMetric(
            labels={"type": "parent"},
            data=[mock_child_metric],
            direct_non_list_metric=mock_child_metric_two,
        )
        mock_child_metric.metric_a += 1
        mock_child_metric.metric_b += 1
        mock_parent_metric.more_data += 1
        mock_child_metric.calculated_metric += 2
        mock_child_metric_two.metric_a += 1
        mock_child_metric_two.calculated_metric += 1

        exposed_metrics = mock_parent_metric.expose()
        expected_metrics = {
            "logprep_calculated_metric;type:child": 4.0,
            "logprep_calculated_metric;type:child2": 2.0,
            "logprep_combined_metric;type:child": 2.0,
            "logprep_combined_metric;type:child2": 1.0,
            "logprep_metric_a;type:child": 1.0,
            "logprep_metric_a;type:child2": 1.0,
            "logprep_metric_b;type:child": 1.0,
            "logprep_metric_b;type:child2": 0.0,
            "logprep_more_data;type:parent": 1.0,
        }
        assert exposed_metrics == expected_metrics

    def test_resets_statistic_sets_everything_to_zero(self):
        mock_child_metric = MockChildMetric(labels={"type": "child"})
        mock_child_metric_two = MockChildMetric(labels={"type": "child2"})
        mock_parent_metric = MockParentMetric(
            labels={"type": "parent"},
            data=[mock_child_metric],
            direct_non_list_metric=mock_child_metric_two,
        )
        mock_child_metric.metric_a += 1
        mock_child_metric.metric_b += 1.2
        mock_parent_metric.more_data += 1
        mock_child_metric.calculated_metric += 2
        mock_child_metric_two.metric_a += 1
        mock_child_metric_two.calculated_metric += 1

        assert mock_child_metric.metric_a == 1
        assert mock_child_metric.metric_b == 1.2
        assert mock_child_metric.combined_metric == 2.2
        assert mock_child_metric.calculated_metric == 4
        assert mock_child_metric_two.metric_a == 1
        assert mock_child_metric_two.metric_b == 0
        assert mock_child_metric_two.combined_metric == 1
        assert mock_child_metric_two.calculated_metric == 2
        assert mock_parent_metric.more_data == 1

        mock_parent_metric.reset_statistics()

        assert mock_child_metric.metric_a == 0
        assert mock_child_metric.metric_b == 0.0
        assert mock_child_metric.combined_metric == 0
        assert mock_child_metric.calculated_metric == 0
        assert mock_child_metric_two.metric_a == 0
        assert mock_child_metric_two.metric_b == 0
        assert mock_child_metric_two.combined_metric == 0
        assert mock_child_metric_two.calculated_metric == 0
        assert mock_parent_metric.more_data == 0

    def test_calculate_new_average_returns_correct_result(self):
        samples = [2, 4, 6, 8, 1, 3, 9]
        current_average = 0
        for i, next_sample in enumerate(samples):
            current_average, _ = calculate_new_average(current_average, next_sample, i)

            real_mean = np.mean(samples[: i + 1])
            assert current_average == real_mean

    def test_get_settable_metrics(self):
        mock_child_metric = MockChildMetric(labels={"type": "child"})
        metrics = get_settable_metrics(mock_child_metric)
        expected_metrics = {
            "_labels": {"type": "child"},
            "_prefix": "logprep_",
            "metric_a": 0,
            "metric_b": 0.0,
            "_calculated_metric": 0,
            "_private_ignore_metric": 0,
            "calculated_metric": 0,
        }
        assert metrics == expected_metrics
