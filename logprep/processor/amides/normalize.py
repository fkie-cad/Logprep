"""This module enables command line normalization of incoming command lines."""

from typing import List

from logprep.processor.amides.features import (
    AnyWordCharacter,
    FilterDummyCharacters,
    Lowercase,
    NumericValues,
    Preprocessor,
    Strings,
    TokenFilter,
    Tokenizer,
)


class CommandLineNormalizer:
    """CommandLineNormalizer normalizes given command lines for
    classification by the misuse detector."""

    __slots__ = ("_filter_dummy", "_lower", "_any_word", "_numeric_values", "_strings")

    _filter_dummy: Preprocessor
    _lower: Preprocessor
    _any_word: Tokenizer
    _numeric_values: TokenFilter
    _strings: TokenFilter

    def __init__(self, max_num_values_length: int, max_str_length: int):
        self._filter_dummy = FilterDummyCharacters()
        self._lower = Lowercase()
        self._any_word = AnyWordCharacter()
        self._numeric_values = NumericValues(length=max_num_values_length)
        self._strings = Strings(length=max_str_length)

    def normalize(self, cmdline: str) -> str:
        """Normalize given cmdline-string by
        (1) Removing dummy characters
        (2) Splitting string into any-word-character tokens
        (3) Removing tokens longer than 30 characters and
        (hex-) numerical values longer than 3 characters.

        Parameters
        ----------
        cmdline: str
            The command line string to be normalized

        Returns
        -------
        tokens_csv: str
            Comma-separated list of tokens extracted by the normalizer.
        """
        preprocessed = self._preprocess(cmdline)
        tokens = self._tokenize(preprocessed)
        filtered_tokens = self._filter_tokens(tokens)

        filtered_tokens.sort()
        tokens_csv = ",".join(filtered_tokens)

        return tokens_csv

    def _preprocess(self, cmdline: str) -> str:
        return self._lower(self._filter_dummy(cmdline))

    def _tokenize(self, preprocessed: str) -> str:
        return self._any_word(preprocessed)

    def _filter_tokens(self, tokens: List[str]) -> str:
        return self._strings(self._numeric_values(tokens))
