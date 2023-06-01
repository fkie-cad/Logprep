"""This module contains all filter expressions used for matching rules."""

import re
from abc import ABC, abstractmethod
from itertools import chain, zip_longest
from typing import List, Any


class FilterExpressionError(BaseException):
    """Base class for FilterExpression related exceptions."""


class KeyDoesNotExistError(FilterExpressionError):
    """Raise if key does not exist in document."""


class FilterExpression(ABC):
    """Base class for all filter expression used for matching rules."""

    def matches(self, document: dict) -> bool:
        """Receives a document and returns True if it is matched by the expression.

        This is a thin wrapper that only ensures that document is a dict and returns False in case a
        KeyDoesNotExistError occurs (you may catch that exception earlier to do something else in
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
        if not isinstance(document, dict):
            return False

        try:
            return self.does_match(document)
        except KeyDoesNotExistError:
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

    # Return the value for the given key from
    # the document.
    @staticmethod
    def _get_value(key: List[str], document: dict) -> Any:
        if not key:
            raise KeyDoesNotExistError

        current = document
        for item in key:
            if item not in current:
                raise KeyDoesNotExistError
            current = current[item]
        return current

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        if not self.__dict__ == other.__dict__:
            return False
        return True

    @staticmethod
    def as_dotted_string(key_list: List[str]) -> str:
        """Converts list of keys to dotted string.

        Parameters
        ----------
        key_list : List[str]
            List of keys.

        Returns
        -------
        str
            Returns dotted string.

        """
        return ".".join([str(i) for i in key_list])

    def get_lucene_filter(self):
        """Returns a filter string that is partially lucene complete. As lucene does not support
        regex the corresponding regex field is left as a value inside the lucene filter such that
        the end user can decide for themselves what they want to do with this information"""
        return str(self)


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

    def get_lucene_filter(self):
        if self._value:
            return "*"
        return ""


class Not(FilterExpression):
    """Filter expression that negates a match."""

    def __init__(self, expression: FilterExpression):
        self.expression = expression

    def __repr__(self) -> str:
        return f"NOT({str(self.expression)})"

    def get_lucene_filter(self):
        return f"NOT ({self.expression.get_lucene_filter()})"

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

    def get_lucene_filter(self):
        return f'({" AND ".join([exp.get_lucene_filter() for exp in self.expressions])})'

    def does_match(self, document: dict) -> bool:
        return all((expression.matches(document) for expression in self.expressions))


class Or(CompoundFilterExpression):
    """Compound filter expression that is a logical disjunction."""

    def __repr__(self) -> str:
        return f'OR({", ".join([str(i) for i in self.expressions])})'

    def get_lucene_filter(self):
        return f'({" OR ".join([exp.get_lucene_filter() for exp in self.expressions])})'

    def does_match(self, document: dict) -> bool:
        return any((expression.matches(document) for expression in self.expressions))


class KeyValueBasedFilterExpression(FilterExpression):
    """Base class of filter expressions that match a certain value on a given key."""

    def __init__(self, key: List[str], expected_value: Any):
        self.key = key
        self._expected_value = expected_value

    def __repr__(self) -> str:
        return f"{self.as_dotted_string(self.key)}:{str(self._expected_value)}"

    def get_lucene_filter(self):
        return str(self)

    def does_match(self, document):
        raise NotImplementedError


class StringFilterExpression(KeyValueBasedFilterExpression):
    """Key value filter expression that matches for a string."""

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)

        if isinstance(value, list):
            return self._expected_value in value
        return str(value) == self._expected_value

    def __repr__(self) -> str:
        return f'{self.as_dotted_string(self.key)}:"{str(self._expected_value)}"'

    def get_lucene_filter(self):
        return str(self)


class WildcardStringFilterExpression(KeyValueBasedFilterExpression):
    """Key value filter expression that matches for a string with wildcard support."""

    flags = 0

    wc = re.compile(r"((?:\\)*\*)")
    wq = re.compile(r"((?:\\)*\?)")

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
            return any(filter(self._matcher.match, (str(val) for val in value)))

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
        return f'{self.as_dotted_string(self.key)}:"{self._expected_value}"'


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


class RangeBasedFilterExpression(FilterExpression):
    """Base class of filter expressions that match for a range of values."""

    def __init__(self, key: List[str], lower_bound: float, upper_bound: float):
        self.key = key
        self._lower_bound = lower_bound
        self._upper_bound = upper_bound

    def __repr__(self) -> str:
        return f"{self.as_dotted_string(self.key)}:[{self._lower_bound} TO {self._upper_bound}]"

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


class RegExFilterExpression(FilterExpression):
    """Filter expression that matches a value using regex."""

    match_escaping_pattern = re.compile(r".*?(?P<escaping>\\*)\$$")
    match_parts_pattern = re.compile(r"^(?P<flag>\(\?\w\))?(?P<start>\^)?(?P<pattern>.*)")

    def __init__(self, key: List[str], regex: str):
        self.key = key
        self._regex = self._normalize_regex(regex)
        self._matcher = re.compile(self._regex)

    def __repr__(self) -> str:
        return f"{self.as_dotted_string(self.key)}:r/{self._regex}/"

    @staticmethod
    def _normalize_regex(regex: str) -> str:
        match = RegExFilterExpression.match_escaping_pattern.match(regex)
        if match and len(match.group("escaping")) % 2 == 0:
            end_token = ""
        else:
            end_token = "$"
        match = RegExFilterExpression.match_parts_pattern.match(regex)
        flag, _, pattern = match.groups()
        flag = "" if flag is None else flag
        pattern = "" if pattern is None else pattern
        return rf"{flag}^{pattern}{end_token}"

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)

        if isinstance(value, list):
            return any(filter(self._matcher.match, value))
        return self._matcher.match(str(value)) is not None

    def get_lucene_filter(self):
        return str(self)


class Exists(FilterExpression):
    """Filter expression that returns true if a given field exists."""

    def __init__(self, value: list):
        self.split_field = value

    def __repr__(self) -> str:
        return f'"{self.as_dotted_string(self.split_field)}"'

    def get_lucene_filter(self):
        return f"{self}: *"

    def does_match(self, document: dict) -> bool:
        if not self.split_field:
            return False

        try:
            current = document
            for sub_field in self.split_field:
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

    def __init__(self, key: List[str]):
        self.key = key

    def __repr__(self) -> str:
        return f"{self.as_dotted_string(self.key)}:{None}"

    def does_match(self, document: dict) -> bool:
        value = self._get_value(self.key, document)
        return value is None
