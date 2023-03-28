"""This module contains all filter expressions used for matching rules."""

import re
import sys
from abc import ABC, abstractmethod
from itertools import chain, zip_longest
from typing import Any, List


class FilterExpression(ABC):
    """Base class for all filter expression used for matching rules."""

    @staticmethod
    def _get_value(key: List[str], document: dict) -> Any:
        if not key:
            raise KeyError

        current = document
        for item in key:
            if item not in current:
                raise KeyError
            current = current[item]
        return current

    def matches(self, document: dict) -> bool:
        """Receives a document and returns True if it is matched by the expression.

        This is a thin wrapper that only ensures that document is a dict and returns False in case a
        KeyError occurs (you may catch that exception earlier to do something else in
        that case)

        Parameters
        ----------
        document : dict
            Document to match.

        Returns
        -------
        bool
            Returns if document matches or not.

        """
        try:
            return self.does_match(document)
        except (KeyError, ValueError):
            return False

    @abstractmethod
    def does_match(self, document: dict) -> bool:
        """Receives a dictionary and must return True/False

        Based on whether the document matches the given expression.
        The method MUST NOT modify the document.

        Parameters
        ----------
        document : dict
            Document to match.

        Returns
        -------
        bool
            Returns if document matches or not.

        """

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        if not self.__dict__ == other.__dict__:
            return False
        return True

    def __hash__(self) -> int:
        return super().__hash__()


class Always(FilterExpression):
    """Filter expression that can be set to match always or never."""

    def __init__(self, value: Any):
        self._value = value

    def __repr__(self):
        if self._value:
            return "TRUE"
        return "FALSE"

    def does_match(self, document: dict):
        return self._value


class Not(FilterExpression):
    """Filter expression that negates a match."""

    def __init__(self, expression: FilterExpression):
        self.expression = expression

    def __repr__(self) -> str:
        return f"NOT({str(self.expression)})"

    def does_match(self, document: dict) -> bool:
        return not self.expression.matches(document)


class CompoundFilterExpression(FilterExpression):
    """Base class of filter expressions that combine other filter expressions."""

    def __init__(self, *args: FilterExpression):
        self.expressions = args

    def does_match(self, document: dict):
        raise NotImplementedError


class And(CompoundFilterExpression):
    """Compound filter expression that is a logical conjunction."""

    def __repr__(self) -> str:
        return f'AND({", ".join([str(i) for i in self.expressions])})'

    def does_match(self, document: dict) -> bool:
        return all(expression.matches(document) for expression in self.expressions)


class Or(CompoundFilterExpression):
    """Compound filter expression that is a logical disjunction."""

    def __repr__(self) -> str:
        return f'OR({", ".join([str(i) for i in self.expressions])})'

    def does_match(self, document: dict) -> bool:
        return any(expression.matches(document) for expression in self.expressions)


class KeyValueBasedFilterExpression(FilterExpression):
    """Base class of filter expressions that match a certain value on a given key."""

    def __init__(self, dotted_field: str, expected_value: Any):
        self.key = dotted_field.split(".")
        self.dotted_field = dotted_field
        self._intern_segments(dotted_field)
        self._expected_value = expected_value

    def _intern_segments(self, keys: list) -> None:
        """intern strings to improve dict access
        see: https://docs.python.org/3/library/sys.html#sys.intern
        """
        self._interned_strings = {}
        for segment in keys:
            if segment not in self._interned_strings:
                self._interned_strings[segment] = sys.intern(segment)

    def __repr__(self) -> str:
        return f"{self.dotted_field}:{str(self._expected_value)}"

    def does_match(self, document):
        raise NotImplementedError


class StringFilterExpression(KeyValueBasedFilterExpression):
    """Key value filter expression that matches for a string."""

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)
        if isinstance(value, list):
            return any(str(item) == self._expected_value for item in value)
        return str(value) == self._expected_value

    def __repr__(self) -> str:
        return f'{self.dotted_field}:"{self._expected_value}"'


class WildcardStringFilterExpression(KeyValueBasedFilterExpression):
    """Key value filter expression that matches for a string with wildcard support."""

    flags = 0

    wc = re.compile(r".*?((?:\\)*\*).*?")
    wq = re.compile(r".*?((?:\\)*\?).*?")

    def __init__(self, key: List[str], expected_value: Any):
        super().__init__(key, expected_value)
        new_string = re.escape(str(self._expected_value))

        matches = self.wq.findall(new_string)
        new_string = self._replace_wildcard(new_string, matches, r"\?", ".?")

        matches = self.wc.findall(new_string)
        new_string = self._replace_wildcard(new_string, matches, r"\*", ".*")

        self.escaped_expected = self._normalize_regex(new_string)
        self._matcher = re.compile(self.escaped_expected, flags=self.flags)

    @staticmethod
    def _normalize_regex(regex: str) -> str:
        return f"^{regex}$"

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)
        if isinstance(value, list):
            return any(self._matcher.match(str(item)) for item in value)
        match_result = self._matcher.match(str(value))

        return match_result is not None

    @staticmethod
    def _replace_wildcard(expected, matches, symbol, wildcard):
        for idx, match in enumerate(matches):
            length = len(match) - 2
            if length == 0:
                matches[idx] = wildcard
            elif length == 2:
                matches[idx] = match[:-4] + symbol
            elif length > 2:
                matches[idx] = match[:-4] + wildcard
        split = re.split(r"(?:\\)*" + symbol, expected)
        return "".join([x for x in chain.from_iterable(zip_longest(split, matches)) if x])

    def __repr__(self) -> str:
        return f'{self.dotted_field}:"{self._expected_value}"'


class SigmaFilterExpression(WildcardStringFilterExpression):
    """Key value filter expression for strings with wildcard support that is case-insensitive."""

    flags = re.IGNORECASE


class IntegerFilterExpression(KeyValueBasedFilterExpression):
    """Key value filter expression that matches for an integer."""

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)

        return value == self._expected_value


class FloatFilterExpression(KeyValueBasedFilterExpression):
    """Key value filter expression that matches for a float."""

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)

        return value == self._expected_value


class RangeBasedFilterExpression(KeyValueBasedFilterExpression):
    """Base class of filter expressions that match for a range of values."""

    def __init__(self, dotted_field: str, lower_bound: float, upper_bound: float):
        super().__init__(dotted_field, None)
        self._lower_bound = lower_bound
        self._upper_bound = upper_bound

    def __repr__(self) -> str:
        return f"{self.dotted_field}:[{self._lower_bound} TO {self._upper_bound}]"

    def does_match(self, document: dict):
        raise NotImplementedError


class IntegerRangeFilterExpression(RangeBasedFilterExpression):
    """Range based filter expression that matches for integers."""

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)

        return self._lower_bound <= value <= self._upper_bound


class FloatRangeFilterExpression(RangeBasedFilterExpression):
    """Range based filter expression that matches for floats."""

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)

        return self._lower_bound <= value <= self._upper_bound


class RegExFilterExpression(KeyValueBasedFilterExpression):
    """Filter expression that matches a value using regex."""

    def __init__(self, key: str, regex: str):
        super().__init__(key, regex)
        self._regex = self._normalize_regex(regex)
        self._matcher = re.compile(self._regex)

    def __repr__(self) -> str:
        return f"{self.dotted_field}:r/{self._regex}/"

    @staticmethod
    def _normalize_regex(regex: str) -> str:
        match = re.match(r".*?(?P<escaping>\\*)\$$", regex)
        if match and len(match.group("escaping")) % 2 == 0:
            end_token = ""
        else:
            end_token = "$"
        match = re.match(r"^(?P<flag>\(\?\w\))?(?P<start>\^)?(?P<pattern>.*)", regex)
        flag, _, pattern = match.groups()
        flag = "" if flag is None else flag
        pattern = "" if pattern is None else pattern
        return rf"{flag}^{pattern}{end_token}"

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)
        if isinstance(value, list):
            return any(self._matcher.match(str(item)) for item in value)
        return self._matcher.match(str(value)) is not None


class Exists(FilterExpression):
    """Filter expression that returns true if a given field exists."""

    def __init__(self, dotted_field: str):
        self.dotted_field = dotted_field
        self.key = dotted_field.split(".")

    def __repr__(self) -> str:
        return f'"{self.dotted_field}"'

    def does_match(self, document: dict) -> bool:
        if not self.key:
            return False

        try:
            current = document
            for sub_field in self.key:
                if (
                    sub_field not in current.keys()
                ):  # .keys() is important as it is used to "check" for dict
                    return False
                current = current[sub_field]
            # Don't check for dict instance, instead just "try" for better performance
        except AttributeError as error:
            if "has no attribute 'keys'" not in error.args[0]:
                raise error
            return False

        return True


class Null(FilterExpression):
    """Filter expression that returns true if a given field is set to null."""

    def __init__(self, dotted_field: str):
        self.dotted_field = dotted_field
        self.key = dotted_field.split(".")

    def __repr__(self) -> str:
        return f"{self.key}:{None}"

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)
        return value is None
