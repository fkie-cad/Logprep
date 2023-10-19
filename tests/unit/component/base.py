# pylint: disable=missing-docstring
# pylint: disable=protected-access
import itertools
from abc import ABC
from functools import partial
from logging import getLogger
from typing import Callable, Iterable
from unittest import mock

from attrs import asdict

from logprep.abc.component import Component
from logprep.abc.connector import Connector
from logprep.factory import Factory
from logprep.metrics.metrics import Metric
from logprep.util.helper import camel_to_snake


class BaseComponentTestCase(ABC):
    CONFIG: dict = {}
    object: Connector = None
    logger = getLogger()

    def setup_method(self) -> None:
        config = {"Test Instance Name": self.CONFIG}
        self.object = Factory.create(configuration=config, logger=self.logger)

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
        metric_attributes = asdict(self.object.metrics, filter=self.asdict_filter, recurse=False)
        pairs = itertools.combinations(metric_attributes.values(), 2)
        for metric1, metric2 in pairs:
            assert metric1.name != metric2.name, f"{metric1.name} == {metric2.name}"

    def test_custom_metrics_adds_custom_prefix_to_metrics_name(self):
        block_list = [
            "_labels",
            "_prefix",
            "processing_time_per_event",
            "number_of_processed_events",
        ]
        metric_attributes = asdict(
            self.object.metrics,
            filter=partial(self.asdict_filter, block_list=block_list),
            recurse=False,
        )
        for attribute in metric_attributes.values():
            assert attribute.fullname.startswith(
                f"logprep_{camel_to_snake(self.object.__class__.__name__)}"
            ), f"{attribute.fullname}, logprep_{camel_to_snake(self.object.__class__.__name__)}"
