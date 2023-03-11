# pylint: disable=missing-docstring
# pylint: disable=protected-access
import base64
import json
import zlib
from abc import ABC
from copy import deepcopy
from logging import getLogger
from typing import Iterable
from unittest import mock

import arrow

from logprep.abc.connector import Connector
from logprep.abc.input import Input
from logprep.abc.output import Output
from logprep.factory import Factory
from logprep.util.helper import camel_to_snake
from logprep.util.time_measurement import TimeMeasurement


class BaseCompontentTestCase(ABC):
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

    def test_schedules_tasks(self):
        mock_task = mock.MagicMock()
        self.object._schedule_task(task=mock_task, seconds=1)
        with mock.patch("schedule.Job.should_run", return_value=True):
            self.object.run_pending_tasks()
        mock_task.assert_called()
