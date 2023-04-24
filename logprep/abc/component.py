""" abstract module for components"""
from abc import ABC
from logging import Logger
from typing import Callable

import msgspec
from attr import define, field, validators
from schedule import Scheduler

from logprep.util.helper import camel_to_snake


class Component(ABC):
    """Abstract Component Class to define the Interface"""

    @define(kw_only=True, slots=False)
    class Config:
        """Common Configurations"""

        type: str = field(validator=validators.instance_of(str))
        """Type of the component"""

    # __dict__ is added to support functools.cached_property
    __slots__ = ["name", "_logger", "_config", "__dict__"]

    name: str
    _scheduler = Scheduler()

    _logger: Logger
    _config: Config
    _decoder: msgspec.json.Decoder = msgspec.json.Decoder()
    _encoder: msgspec.json.Encoder = msgspec.json.Encoder()

    def __init__(self, name: str, configuration: "Component.Config", logger: Logger):
        self._logger = logger
        self._config = configuration
        self.name = name

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
