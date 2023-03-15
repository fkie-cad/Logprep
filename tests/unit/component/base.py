# pylint: disable=missing-docstring
# pylint: disable=protected-access
from abc import ABC
from logging import getLogger
from typing import Iterable
from unittest import mock

from logprep.abc.component import Component
from logprep.abc.connector import Connector
from logprep.factory import Factory
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
