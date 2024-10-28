""" abstract module for components"""

import functools
import inspect
import logging
import sys
import time
from abc import ABC
from functools import cached_property
from typing import Callable

import msgspec
from attr import define, field, validators
from attrs import asdict
from schedule import Scheduler

from logprep.metrics.metrics import Metric
from logprep.util.defaults import DEFAULT_HEALTH_TIMEOUT, EXITCODES
from logprep.util.helper import camel_to_snake

logger = logging.getLogger("Component")


class Component(ABC):
    """Abstract Component Class to define the Interface"""

    @define(kw_only=True, slots=False, frozen=True)
    class Config:
        """Common Configurations
        This class is used to define the configuration of the component.
        It is frozen because the configuration should not be changed after initialization.
        """

        type: str = field(validator=validators.instance_of(str))
        """Type of the component"""

        health_timeout: float = field(
            validator=validators.instance_of(float),
            default=DEFAULT_HEALTH_TIMEOUT,
            converter=float,
        )
        """Timeout in seconds for health check: Default is 1 seconds"""

    @define(kw_only=True)
    class Metrics:
        """Base Metric class to track and expose statistics about logprep"""

        _labels: dict

        def __attrs_post_init__(self):
            for attribute in asdict(self):
                attribute = getattr(self, attribute)
                if isinstance(attribute, Metric):
                    attribute.labels = self._labels
                    attribute.init_tracker()

    # __dict__ is added to support functools.cached_property
    __slots__ = ["name", "_config", "pipeline_index", "__dict__"]

    # instance attributes
    name: str
    pipeline_index: int
    _config: Config

    # class attributes
    _scheduler = Scheduler()
    _decoder: msgspec.json.Decoder = msgspec.json.Decoder()
    _encoder: msgspec.json.Encoder = msgspec.json.Encoder()

    @property
    def metric_labels(self) -> dict:
        """Labels for the metrics"""
        return {"component": self._config.type, "name": self.name, "description": "", "type": ""}

    def __init__(self, name: str, configuration: "Component.Config", pipeline_index: int = None):
        self._config = configuration
        self.name = name
        self.pipeline_index = pipeline_index

    @cached_property
    def metrics(self):
        """create and return metrics object"""
        return self.Metrics(labels=self.metric_labels)

    def __repr__(self):
        return camel_to_snake(self.__class__.__name__)

    def describe(self) -> str:
        """Provide a brief name-like description of the connector.

        The description is indicating its type _and_ the name provided when creating it.

        Examples
        --------

        >>> ConfluentKafkaInput(name)

        """
        return f"{self.__class__.__name__} ({self.name})"

    def setup(self):
        """Set the component up."""
        self._populate_cached_properties()
        if not "http" in self._config.type:
            # HTTP input connector spins up a http server
            # only on the first pipeline process
            # but this runs on all pipeline processes which leads to never
            # completing the setup phase
            self._wait_for_health()

    def _wait_for_health(self) -> None:
        """Wait for the component to be healthy.
        if the component is not healthy after a period of time, the process will exit.
        """
        for i in range(3):
            if self.health():
                break
            logger.info("Wait for %s initially becoming healthy: %s/3", self.name, i + 1)
            time.sleep(1 + i)
        else:
            logger.error("Component '%s' did not become healthy", self.name)
            sys.exit(EXITCODES.PIPELINE_ERROR.value)

    def _populate_cached_properties(self):
        _ = [
            getattr(self, name)
            for name, value in inspect.getmembers(self)
            if isinstance(value, functools.cached_property)
        ]

    def shut_down(self):
        """Stop processing of this component.

        Optional: Called when stopping the pipeline

        """
        if hasattr(self, "__dict__"):
            self.__dict__.clear()

    def health(self) -> bool:
        """Check the health of the component.

        Returns
        -------
        bool
            True if the component is healthy, False otherwise.

        """
        logger.debug("Checking health of %s", self.name)
        return True

    def _schedule_task(
        self, task: Callable, seconds: int, args: tuple = None, kwargs: dict = None
    ) -> None:
        """Schedule a task to run periodically during pipeline run.
        The task is run in :code:`pipeline.py` in the :code:`process_pipeline` method.

        Parameters
        ----------

        task: Callable
            a callable to run

        args: tuple, optional
            the arguments for the Callable

        kwargs: dict, optional
            the keyword arguments for the Callable

        seconds: int
            the time interval in seconds

        """
        if task in map(lambda job: job.job_func.func, self._scheduler.jobs):
            return
        args = () if args is None else args
        kwargs = {} if kwargs is None else kwargs
        self._scheduler.every(seconds).seconds.do(task, *args, **kwargs)

    @classmethod
    def run_pending_tasks(cls) -> None:
        """Starts all pending tasks. This is called in :code:`pipeline.py`"""
        cls._scheduler.run_pending()
