"""Logprep time helpers module"""

from datetime import UTC, datetime, tzinfo
from enum import IntEnum

from logprep.abc.exceptions import LogprepException


class TimeParserException(LogprepException):
    """Exception class for time parsing"""


class UnixTimestampLength(IntEnum):
    """Digit lengths of common UNIX timestamp representations."""

    SECONDS = 10
    MILLISECONDS = 13
    MICROSECONDS = 16
    NANOSECONDS = 19


class TimeParser:
    """Encapsulation of time related methods"""

    @classmethod
    def from_string(cls, source: str, set_missing_utc: bool = True) -> datetime:
        """Parses input string to datetime object.

        Parameters
        ----------
        source : str
            Input string in ISO8601 format
        set_missing_utc : bool
            Set timezone to utc if it is missing and this is true

        Returns
        -------
        datetime
            Datetime object

        Raises
        ------
        TimeParserException
            Raises if source can't be parsed as datetime object from ISO8601 format
        """
        try:
            time_object = datetime.fromisoformat(source)  # pylint: disable=c-extension-no-member
            if set_missing_utc:
                time_object = cls._set_utc_if_timezone_is_missing(time_object)
            return time_object
        except ValueError as error:
            raise TimeParserException(str(error)) from error

    @classmethod
    def from_unix_timestamp(cls, timestamp: int | float) -> datetime:
        """Get datetime from unix timestamp.

        Parameters
        ----------
        timestamp : int | float
            Unix timestamp

        Returns
        -------
        datetime
            Datetime object

        Raises
        ------
        TimeParserException
            Raises if timestamp can't be parsed as datetime object from unix timestamp format
        """
        try:
            time_object = datetime.fromtimestamp(timestamp, tz=UTC)
            time_object = cls._set_utc_if_timezone_is_missing(time_object)
            return time_object
        except TypeError as error:
            raise TimeParserException(str(error)) from error

    @staticmethod
    def now(timezone: tzinfo | None = UTC) -> datetime:
        """Returns the current time.

        Parameters
        ----------
        timezone : tzinfo | None
            The timezone to use for the timestamp

        Returns
        -------
        datetime
            Current date and time as datetime
        """
        timezone = timezone if timezone else UTC
        time_object = datetime.now(timezone)
        return time_object

    @classmethod
    def from_format(cls, source: str, format_str: str, set_missing_utc: bool = True) -> datetime:
        """Parse date from format.

        Parameters
        ----------
        source : str
            The date string
        format_str : str
            The format string
        set_missing_utc : bool
            Set timezone to utc if it is missing and this is true

        Returns
        -------
        datetime
            The datetime object

        Raises
        ------
        TimeParserException
            Raised if something could not be parsed
        """
        try:
            time_object = datetime.strptime(source, format_str)
            if set_missing_utc:
                time_object = cls._set_utc_if_timezone_is_missing(time_object)
            return time_object
        except ValueError as error:
            raise TimeParserException(str(error)) from error

    @staticmethod
    def _set_utc_if_timezone_is_missing(time_object: datetime) -> datetime:
        if time_object.tzinfo is None:
            time_object = time_object.replace(tzinfo=UTC)
        return time_object

    @staticmethod
    def _normalize_unix_timestamp_to_seconds(timestamp: str) -> int | float:
        """Normalize a UNIX timestamp string to seconds.

        The precision is inferred from the digits before the decimal point. Supported
        precisions are seconds, milliseconds, microseconds, and nanoseconds. Fractional
        timestamps are parsed as float to preserve sub-second precision.

        Raises
        ------
        TimeParserException
            Raised if the timestamp cannot be parsed or has an unsupported length.
        """

        try:
            timestamp = timestamp.strip()
            timestamp_parts = timestamp.split(".", maxsplit=1)
            integer_part = timestamp_parts[0]
            has_fractional_part = len(timestamp_parts) == 2

            divisor = TimeParser._get_unix_timestamp_normalization_divisor(integer_part)
            value = float(timestamp) if has_fractional_part else int(timestamp)

            if divisor == 1:
                return value

            return value / divisor
        except ValueError as error:
            raise TimeParserException(str(error)) from error

    @staticmethod
    def _get_unix_timestamp_integer_part(timestamp: str) -> str:
        """Return the integer part of a UNIX timestamp."""
        return timestamp.split(".", maxsplit=1)[0]

    @staticmethod
    @staticmethod
    def _get_unix_timestamp_normalization_divisor(integer_part: str) -> int:
        """Return the divisor for normalizing a supported UNIX timestamp to seconds."""

        integer_part_length = len(integer_part)

        if integer_part_length <= UnixTimestampLength.SECONDS:
            return 1

        scalable_unix_timestamp_lengths = frozenset(
            int(length) for length in UnixTimestampLength if length > UnixTimestampLength.SECONDS
        )

        if integer_part_length in scalable_unix_timestamp_lengths:
            return 10 ** (integer_part_length - UnixTimestampLength.SECONDS)

        raise ValueError(f"Unsupported Unix timestamp length: {integer_part_length}")

    @staticmethod
    def _normalize_fractional_unix_timestamp_to_seconds(timestamp: str, divisor: int) -> float:
        """Normalize a fractional UNIX timestamp to seconds.

        Fractional UNIX timestamps are parsed as float to preserve sub-second
        precision.
        """
        return float(timestamp) / divisor

    @staticmethod
    def _normalize_integer_unix_timestamp_to_seconds(timestamp: str, divisor: int) -> int | float:
        """Normalize an integer-only UNIX timestamp to seconds."""
        parsed_timestamp = int(timestamp)

        if divisor == 1:
            return parsed_timestamp

        return parsed_timestamp / divisor

    @classmethod
    def parse_datetime(
        cls, timestamp: str, source_format: str, source_timezone: tzinfo
    ) -> datetime:
        """Parse a timestamp based on different formats.

        A format string, 'ISO8601' and 'UNIX' are allowed formats.

        Parameters
        ----------
        timestamp : str
            The timestamp string that should be parsed
        source_format : str
            The format which should be used to parse the timestamp string. Besides a format string
            'ISO8601' and 'UNIX' are allowed formats.
        source_timezone : tzinfo


        Returns
        -------
        datetime
            The parsed timestamp as datetime object.
        """
        if source_format == "UNIX":
            normalized_unix_timestamp = cls._normalize_unix_timestamp_to_seconds(timestamp)
            parsed_datetime = cls.from_unix_timestamp(normalized_unix_timestamp)
        elif source_format == "ISO8601":
            parsed_datetime = cls.from_string(timestamp, set_missing_utc=False)
        else:
            parsed_datetime = cls.from_format(timestamp, source_format, set_missing_utc=False)
            if parsed_datetime.year == 1900:
                parsed_datetime = parsed_datetime.replace(year=datetime.now().year)

        if parsed_datetime.tzinfo is None:
            parsed_datetime = parsed_datetime.replace(tzinfo=source_timezone)

        return parsed_datetime
