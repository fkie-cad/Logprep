# pylint: disable=too-few-public-methods
# -> deactivate temporarily pylint issue here

"""abstract module for event related datatypes"""

from abc import ABC


class EventMetadata(ABC):
    """Abstract EventMetadata Class to define the Interface"""
