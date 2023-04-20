"""logprep time helpers module"""
from datetime import datetime

import ciso8601
import pendulum


def parse_timestamp(source: str) -> datetime:
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
