# pylint: disable=missing-docstring
# pylint: disable=protected-access
import itertools
from abc import ABC
from functools import partial
from logging import getLogger
from typing import Callable, Iterable
from unittest import mock

import pytest
from attrs import asdict
from attrs.exceptions import FrozenInstanceError
from prometheus_client import Counter, Gauge, Histogram

from logprep.abc.component import Component
from logprep.factory import Factory
from logprep.metrics.metrics import Metric
from logprep.util.helper import camel_to_snake


class BaseComponentTestCase(ABC):
    CONFIG: dict = {}
    object: Component = None
    logger = getLogger()
    expected_metrics: list = []

    block_list = [
        "_labels",
        "_prefix",
    ]

    metric_attributes: dict

    def setup_method(self) -> None:
        config = {"Test Instance Name": self.CONFIG}
        self.object = Factory.create(configuration=config)
        self.object._wait_for_health = mock.MagicMock()
        assert "metrics" not in self.object.__dict__, "metrics should be a cached_property"
        self.metric_attributes = asdict(
            self.object.metrics,
            filter=partial(self.asdict_filter, block_list=self.block_list),
            recurse=False,
        )

    def test_uses_python_slots(self):
        assert isinstance(self.object.__slots__, Iterable)

    def test_describe(self):
        describe_string = self.object.describe()
        expected_base_description = f"{self.object.__class__.__name__} (Test Instance Name)"
        assert describe_string.startswith(expected_base_description)

    def test_snake_type(self):
        assert str(self.object) == camel_to_snake(self.object.__class__.__name__)

    def test_schedules_and_runs_tasks(self):
        mock_task = mock.MagicMock()
        self.object._schedule_task(task=mock_task, seconds=1)
        with mock.patch("schedule.Job.should_run", return_value=True):
            self.object.run_pending_tasks()
        mock_task.assert_called()

    def test_schedules_tasks_only_once(self):
        mock_task = mock.MagicMock()
        self.object._schedule_task(task=mock_task, seconds=1)
        job_count = len(Component._scheduler.jobs)
        self.object._schedule_task(task=mock_task, seconds=1)
        assert job_count == len(Component._scheduler.jobs)

    @staticmethod
    def asdict_filter(attribute, value, block_list=None):
        """Returns all attributes not in block list or None"""
        if block_list is None:
            block_list = ["_labels", "_prefix"]
        return not any((attribute.name in block_list, value is None, isinstance(value, Callable)))

    def test_custom_metrics_are_metric_objects(self):
        metric_attributes = asdict(self.object.metrics, filter=self.asdict_filter, recurse=False)
        assert all(
            isinstance(value, Metric) for value in metric_attributes.values()
        ), "one of the metrics instance attributes is not an instance of type Metric"

    def test_no_metrics_with_same_name(self):
        pairs = itertools.combinations(self.metric_attributes.values(), 2)
        for metric1, metric2 in pairs:
            assert metric1.name != metric2.name, f"{metric1.name} == {metric2.name}"

    def test_custom_metrics_adds_custom_prefix_to_metrics_name(self):
        for attribute in self.metric_attributes.values():
            assert attribute.fullname.startswith(
                "logprep_"
            ), f"{attribute.fullname}, logprep_{camel_to_snake(self.object.__class__.__name__)}"

    def test_expected_metrics_attributes(self):
        for expected_metric in self.expected_metrics:
            metric_name = expected_metric.replace(
                f"logprep_{camel_to_snake(self.object.__class__.__name__)}_", ""
            )
            metric_name = metric_name.replace("logprep_", "")
            metric_attribute = getattr(self.object.metrics, metric_name)
            assert metric_attribute is not None
            assert isinstance(metric_attribute, Metric)

    def test_expected_metrics_attributes_are_initialized(self):
        for expected_metric in self.expected_metrics:
            metric_name = expected_metric.replace(
                f"logprep_{camel_to_snake(self.object.__class__.__name__)}_", ""
            )
            metric_name = metric_name.replace("logprep_", "")
            metric_attribute = getattr(self.object.metrics, metric_name)
            assert metric_attribute.tracker is not None
            possibile_tracker_types = (Counter, Gauge, Histogram)
            assert isinstance(metric_attribute.tracker, possibile_tracker_types)

    def test_all_metric_attributes_are_tested(self):
        if self.object.__class__.Metrics is Component.Metrics:
            return
        assert self.expected_metrics, "expected_metrics is empty"
        fullnames = {metric.fullname for metric in self.metric_attributes.values()}
        difference = fullnames.difference(set(self.expected_metrics))
        assert not difference, f"{difference} are not defined in `expected_metrics`"
        assert fullnames == set(self.expected_metrics)

    @mock.patch("inspect.getmembers", return_value=[("mock_prop", lambda: None)])
    def test_setup_populates_cached_properties(self, mock_getmembers):
        self.object.setup()
        mock_getmembers.assert_called_with(self.object)

    def test_setup_calls_wait_for_health(self):
        self.object.setup()
        self.object._wait_for_health.assert_called()

    def test_config_is_immutable(self):
        with pytest.raises(FrozenInstanceError):
            self.object._config.type = "new_type"

    def test_health_returns_bool(self):
        assert isinstance(self.object.health(), bool)
