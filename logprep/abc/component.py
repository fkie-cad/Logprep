""" abstract module for components"""
from abc import ABC
from logging import Logger
from typing import Callable

import msgspec
from attr import define, field, validators
from attrs import asdict
from schedule import Scheduler

from logprep.metrics.metrics import Metric, MetricType
from logprep.util.helper import camel_to_snake


class Component(ABC):
    """Abstract Component Class to define the Interface"""

    @define(kw_only=True, slots=False)
    class Config:
        """Common Configurations"""

        type: str = field(validator=validators.instance_of(str))
        """Type of the component"""

    @define(kw_only=True)
    class Metrics:
        """Base Metric class to track and expose statistics about logprep"""

        _labels: dict
        _prefix: str = "logprep_"

        number_of_processed_events: Metric = field(
            factory=lambda: Metric(
                type=MetricType.COUNTER,
                description="Number of events that were processed",
                name="number_of_processed_events",
            )
        )
        """Number of events that were processed"""

        number_of_failed_events: Metric = field(
            factory=lambda: Metric(
                type=MetricType.COUNTER,
                description="Number of events that were send to error output",
                name="number_of_failed_events",
            )
        )
        """Number of events that were send to error output"""

        def __attrs_post_init__(self):
            for attribute in asdict(self):
                attribute = getattr(self, attribute)
                if isinstance(attribute, Metric):
                    attribute.labels = self._labels
                    attribute.tracker = attribute.type(
                        name=f"{self._prefix}{attribute.name}",
                        documentation=attribute.description,
                        labelnames=attribute.labels.keys(),
                        registry=None,
                    )
                    attribute.tracker.labels(**attribute.labels)

    # __dict__ is added to support functools.cached_property
    __slots__ = ["name", "_logger", "_config", "__dict__"]

    name: str
    _scheduler = Scheduler()

    _logger: Logger
    _config: Config
    _decoder: msgspec.json.Decoder = msgspec.json.Decoder()
    _encoder: msgspec.json.Encoder = msgspec.json.Encoder()

    @property
    def metric_labels(self) -> dict:
        """Labels for the metrics"""
        return {"component": self._config.type, "name": self.name}

    def __init__(self, name: str, configuration: "Component.Config", logger: Logger):
        self._logger = logger
        self._config = configuration
        self.name = name
        self.metrics = self.Metrics(labels=self.metric_labels)

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
        """Set the component up.

        This is optional.

        """

    def shut_down(self):
        """Stop processing of this component.

        Optional: Called when stopping the pipeline

        """
        if hasattr(self, "__dict__"):
            self.__dict__.clear()

    def _schedule_task(
        self, task: Callable, seconds: int, args: tuple = None, kwargs: dict = None
    ) -> None:
        """Schedule a task to run periodicly during pipeline run.
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
