"""logprep time helpers module"""
from datetime import datetime
from typing import Union

import ciso8601
import pendulum


class TimeParser:
    """encapsulation of time related methods"""

    @classmethod
    def from_string(cls, source: str) -> datetime:
        """parses input string to datetime object

        Parameters
        ----------
        source : str
            input string

        Returns
        -------
        datetime
            datetime object
        """
        try:
            return ciso8601.parse_datetime(source)  # pylint: disable=c-extension-no-member
        except ValueError:
            return pendulum.parse(source, strict=False)

    @classmethod
    def from_timestamp(cls, timestamp: Union[int, float]) -> datetime:
        """get datetime from unix timestamp

        Parameters
        ----------
        timestamp : int
            unit timestamp

        Returns
        -------
        datetime
            datetime object
        """
        return pendulum.from_timestamp(timestamp)

    @staticmethod
    def now() -> datetime:
        """returns the current time

        Returns
        -------
        datetime
            current date and time as datetime
        """
        return pendulum.now()

    @staticmethod
    def from_format(source, format_str: str) -> datetime:
        return pendulum.from_format(source, format_str)
