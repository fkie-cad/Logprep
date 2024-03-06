"""This module contains several preprocessing, tokenization,
and token filtering callables to split (raw) documents into a list
of token words.
"""

import re
from abc import ABC, abstractmethod


class Preprocessor(ABC):
    """Abstract base class Preprocessor to perform all kinds of
    preprocessing tasks on given strings."""

    @abstractmethod
    def __call__(self, string: str):
        """Performs the actual preprocessing.

        Parameters
        ---------
        string: str
            The string that is processed.

        Returns
        -------
        :str
            The preprocessed string.
        """

    @property
    @abstractmethod
    def name(self):
        """Returns the name of the preprocessor."""


class FilterDummyCharacters(Preprocessor):
    """FilterDummyCharacters removes all windows-cmdline-related dummy
    characters such as double-quotes ("\""), circumflex ("^"), and other quoting
    characters ("`","’")."""

    def __init__(self):
        super().__init__()
        self._re = r"[\"\^`’]"

    def __call__(self, string: str):
        return re.sub(self._re, "", string)

    @property
    def name(self):
        return "dummy_chars"


class Lowercase(Preprocessor):
    """Lowercase simply turns all strings into lowercase strings."""

    def __call__(self, string: str):
        return string.lower()

    @property
    def name(self):
        return "lowercase"


class Tokenizer(ABC):
    """Tokenizer as ABC for all tokenizers that split given strings
    into list of string-tokens using regular-expressions.
    """

    def __call__(self, string: str):
        """Performs tokenization on given string.

        Parameters
        ----------
        string: str
            String to be tokenized.

        Returns
        -------
        : List[str]
            List of tokens.
        """

    @property
    @abstractmethod
    def name(self):
        """Returns the tokenizer's name."""


class AnyWordCharacter(Tokenizer):
    """AnyWordCharacter to split string on any letter, digit, or underscore ("\\w+")."""

    def __init__(self):
        super().__init__()
        self._re = r"(\w+)"

    def __call__(self, string: str):
        return re.findall(self._re, string)

    @property
    def name(self):
        return "any_word_char"


class CommaSeparation(Tokenizer):
    """CommaSeparation-Tokenizer to split string on comma(,)-symbols."""

    def __call__(self, string):
        return string.split(",")

    @property
    def name(self):
        return "comma_separation"


class TokenFilter(ABC):
    """Abstract base class TokenFilter to realize filters applied on
    list of tokens."""

    @abstractmethod
    def __call__(self, token_list: list[str]):
        """Filter tokens of given list of tokens.

        Parameters
        ----------
        token_list : List[str]
            List of tokens which should be filtered.

        Returns
        -------
        : List[str]
            Filtered token list.
        """

    @property
    @abstractmethod
    def name(self):
        """Name of the token filter."""


class NumericValues(TokenFilter):
    """NumericValues to filter all (hexa)-decimal values which are longer
    than a given length."""

    def __init__(self, length: int):
        """Init filter.

        Parameters
        ----------
        length: int
            Maximum length of (hex-)numerical values which should not be filtered.
        """
        super().__init__()
        self._re = rf"^(?:0x)?[0-9a-f]{{{length + 1},}}$"

    def __call__(self, token_list):
        tokens = [token for token in token_list if not re.match(self._re, token)]

        return tokens

    @property
    def name(self):
        return "numeric_values"


class Strings(TokenFilter):
    """Strings to filter all tokens which are larger than a specific length."""

    def __init__(self, length):
        """Init the token filter.

        Parameters
        ----------
        length: int
            Length of token strings which should be filtered out.
        """

        super().__init__()
        self._length = length

    def __call__(self, token_list):
        tokens = [token for token in token_list if not len(token) > self._length]

        return tokens

    @property
    def name(self):
        return "string"
