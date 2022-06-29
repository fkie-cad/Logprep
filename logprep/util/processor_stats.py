"""This module contains functionality to log the status of logprep."""
from collections import namedtuple

MetricTargets = namedtuple("MetricTargets", "file_exporter prometheus_exporter")


class StatsClassesController:
    """Used to control if methods of classes for status tracking are enabled or not."""

    ENABLED = False

    @staticmethod
    def decorate_all_methods(decorator):
        """Decorate all methods of a class with another decorator."""

        def decorate(cls):
            for attribute in cls.__dict__:
                if callable(getattr(cls, attribute)):
                    setattr(cls, attribute, decorator(getattr(cls, attribute)))
            return cls

        return decorate

    @staticmethod
    def is_enabled(func):
        """Disable a method if status tracking is disabled."""

        def inner(*args, **kwargs):
            if StatsClassesController.ENABLED:
                return func(*args, **kwargs)
            return None

        return inner
