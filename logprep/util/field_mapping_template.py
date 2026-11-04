"""Compile field mapping templates against static context and evaluate runtime context."""

import inspect
import re
from collections.abc import Collection, Mapping
from copy import deepcopy
from enum import Enum, auto
from typing import Final, TypeAlias, TypeVar, assert_never

from attr import field
from attrs import define

from logprep.abc.exceptions import LogprepException
from logprep.util.field_mapping_template_helpers import DEFAULT_FUNCTIONS, Function
from logprep.util.helper import (
    MISSING,
    FieldValue,
    JsonObject,
    Missing,
    get_dotted_field_list,
    get_field_value,
)

T = TypeVar("T")
ReadonlyList: TypeAlias = tuple[T, ...]

_EXPRESSION_START: Final[str] = "${"
_EXPRESSION_END: Final[str] = "}"
_ESCAPE_CHARACTER: Final[str] = "\\"
_PATH_SEPARATOR: Final[str] = "."
_COMMA_CHARACTER: Final[str] = ","
_EQUAL_CHARACTER: Final[str] = "="
_LPAREN_CHARACTER: Final[str] = "("
_RPAREN_CHARACTER: Final[str] = ")"
_CONVERSION_SEPARATOR: Final[str] = "|"
_SINGLE_QUOTE_CHARACTER: Final[str] = "'"
_DOUBLE_QUOTE_CHARACTER: Final[str] = '"'
_TRUE_VALUE_STRINGS: ReadonlyList[str] = ("true", "True")
_FALSE_VALUE_STRINGS: ReadonlyList[str] = ("false", "False")
_BOOLEAN_VALUE_STRINGS: ReadonlyList[str] = (*_TRUE_VALUE_STRINGS, *_FALSE_VALUE_STRINGS)
_NONE_VALUE_STRINGS: ReadonlyList[str] = ("none", "None")

_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[+-]?[0-9](?:_?[0-9])*" r"(?:\.[0-9](?:_?[0-9])*)?" r"(?:[eE][+-]?[0-9]+)?"
)


class FieldMappingTemplateConfigError(LogprepException):
    """Invalid configuration with an optional zero-based template source position.

    ``position`` is relative to the complete string being scanned or parsed.
    It is ``None`` when the location is unknown
    or the error is not associated with a source character.
    """

    def __init__(self, message: str, *, position: int | None = None) -> None:
        """Store the diagnostic message and its optional source position."""
        super().__init__(message)
        self.position = position


class FieldMappingTemplateEvaluationError(LogprepException):
    """A compiled field mapping template could not be evaluated."""


class FieldMappingTemplateLookupError(FieldMappingTemplateEvaluationError):
    """A required runtime context root or field path could not be resolved.

    Missing fields are skipped when ``skip_missing_fields`` is true; missing
    context roots still raise this error. An explicit ``None`` is a valid value.
    """


class TokenKind(Enum):
    """Distinguish text, expression boundaries and unescaped expression delimiters."""

    TEXT = auto()
    EXPRESSION_START = auto()
    EXPRESSION_END = auto()
    DOT = auto()
    PIPE = auto()
    WHITESPACE = auto()
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    COMMA = auto()
    EQUALS = auto()
    STRING = auto()
    INTEGER = auto()
    FLOAT = auto()
    BOOLEAN = auto()
    NONE = auto()


DELIMITER_TOKENS = {
    _COMMA_CHARACTER: TokenKind.COMMA,
    _EQUAL_CHARACTER: TokenKind.EQUALS,
    _LPAREN_CHARACTER: TokenKind.LEFT_PAREN,
    _RPAREN_CHARACTER: TokenKind.RIGHT_PAREN,
    _PATH_SEPARATOR: TokenKind.DOT,
    _CONVERSION_SEPARATOR: TokenKind.PIPE,
}


@define(frozen=True)
class Token:
    """A scanned value with its kind and zero-based source position."""

    kind: TokenKind
    value: str
    position: int


class Lexer:
    """Scan template strings into tokens for the parser."""

    def __init__(self, template: str, *, key_mode: bool = False) -> None:
        """Start scanning a template; key mode also tokenizes unescaped literal dots."""
        self.template = template
        self.position = 0
        self.tokens: list[Token] = []
        self._key_mode = key_mode

    def _at_value_start(self) -> bool:
        for token in reversed(self.tokens):
            if token.kind is TokenKind.WHITESPACE:
                continue

            return token.kind in (
                TokenKind.EXPRESSION_START,
                TokenKind.LEFT_PAREN,
                TokenKind.COMMA,
                TokenKind.EQUALS,
            )

        return False

    def _scan_text(self, *, in_expression: bool, at_value_start: bool) -> Token:
        start = self.position
        characters: list[str] = []

        while self.position < len(self.template):
            character = self.template[self.position]

            if character == _ESCAPE_CHARACTER:
                if self.position + 1 == len(self.template):
                    raise FieldMappingTemplateConfigError(
                        "Trailing backslash", position=self.position
                    )

                characters.append(self.template[self.position + 1])
                self.position += 2
                continue

            if self._key_mode and not in_expression and character == _PATH_SEPARATOR:
                break

            if self.template.startswith(_EXPRESSION_START, self.position):
                break

            if in_expression:
                if (
                    self.template.startswith(_EXPRESSION_END, self.position)
                    or character in DELIMITER_TOKENS
                    or character.isspace()
                    or character in (_SINGLE_QUOTE_CHARACTER, _DOUBLE_QUOTE_CHARACTER)
                ):
                    break

            characters.append(character)
            self.position += 1

        value = "".join(characters)
        kind = TokenKind.TEXT

        followed_by_path_separator = (
            self.position < len(self.template) and self.template[self.position] == _PATH_SEPARATOR
        )

        if in_expression and at_value_start and not followed_by_path_separator:
            if value in _BOOLEAN_VALUE_STRINGS:
                kind = TokenKind.BOOLEAN
            elif value in _NONE_VALUE_STRINGS:
                kind = TokenKind.NONE

        return Token(kind, value, start)

    def _scan_quoted_string(self) -> Token:
        start = self.position
        quote = self.template[self.position]
        characters: list[str] = []
        self.position += 1

        while self.position < len(self.template):
            character = self.template[self.position]

            if character == quote:
                self.position += 1
                return Token(TokenKind.STRING, "".join(characters), start)

            if character == _ESCAPE_CHARACTER:
                if self.position + 1 == len(self.template):
                    raise FieldMappingTemplateConfigError(
                        "Trailing backslash", position=self.position
                    )

                self.position += 1
                character = self.template[self.position]

            characters.append(character)
            self.position += 1

        raise FieldMappingTemplateConfigError("Unclosed string", position=start)

    def _scan_number(self) -> Token | None:
        number = _NUMBER_PATTERN.match(self.template, self.position)
        if number is None:
            return None

        end = number.end()

        if end < len(self.template):
            following = self.template[end]
            is_delimiter = following in DELIMITER_TOKENS and following != "."

            if not (
                following.isspace()
                or is_delimiter
                or self.template.startswith(_EXPRESSION_END, end)
            ):
                return None

        start = self.position
        value = number.group()
        self.position = end

        if "." in value or "e" in value or "E" in value:
            kind = TokenKind.FLOAT
        else:
            kind = TokenKind.INTEGER

        return Token(kind, value, start)

    def _scan_expression_token(self) -> Token:
        character = self.template[self.position]

        if character in (_SINGLE_QUOTE_CHARACTER, _DOUBLE_QUOTE_CHARACTER):
            return self._scan_quoted_string()

        if self._at_value_start():
            number = self._scan_number()
            if number is not None:
                return number

        if self.template.startswith(_EXPRESSION_END, self.position):
            token = Token(TokenKind.EXPRESSION_END, _EXPRESSION_END, self.position)
            self.position += len(_EXPRESSION_END)
            return token

        kind = DELIMITER_TOKENS.get(character)

        if kind is None and character.isspace():
            kind = TokenKind.WHITESPACE

        if kind is not None:
            token = Token(kind, character, self.position)
            self.position += 1
            return token

        return self._scan_text(in_expression=True, at_value_start=self._at_value_start())

    def scan(self) -> ReadonlyList[Token]:
        """Consume the template, returning tokens with zero-based source positions.

        Backslashes escape the following character without translating escape
        sequences. Unquoted expression punctuation and whitespace become separate
        tokens. Quoted strings and numeric, boolean and none literals have their
        own token kinds; token values remain strings.

        Incomplete escapes and unclosed strings raise
        ``FieldMappingTemplateConfigError``. Expression structure is validated
        by the parser.
        """

        in_expression = False
        while self.position < len(self.template):
            if self.template.startswith(_EXPRESSION_START, self.position):

                token = Token(TokenKind.EXPRESSION_START, _EXPRESSION_START, self.position)
                in_expression = True
                self.position += len(_EXPRESSION_START)
            elif in_expression:
                token = self._scan_expression_token()
                in_expression = token.kind is not TokenKind.EXPRESSION_END
            elif self._key_mode and self.template[self.position] == _PATH_SEPARATOR:
                token = Token(TokenKind.DOT, _PATH_SEPARATOR, self.position)
                self.position += 1
            else:
                token = self._scan_text(in_expression=False, at_value_start=False)

            self.tokens.append(token)

        return tuple(self.tokens)


@define(frozen=True)
class Constant:
    """A prepared value; evaluation deep-copies mutable dict/list values."""

    value: FieldValue

    def compile(
        self, _static_context: dict[str, JsonObject], _functions: Mapping[str, Function]
    ) -> "Constant":
        """Return this already prepared constant unchanged."""
        return self

    def evaluate(
        self, _runtime_context: dict[str, JsonObject], _skip_missing_fields: bool = False
    ) -> FieldValue:
        """Return the prepared value, deep-copying mutable dictionaries and lists."""
        if isinstance(self.value, (dict, list)):
            return deepcopy(self.value)
        return self.value


@define(frozen=True)
class Lookup:
    """A context root and unescaped field path with a compiled copy policy.

    ``copy_result`` deep-copies runtime dictionaries and lists by default.
    Compilation disables it for arguments of functions that can borrow input.
    """

    context: str
    path: tuple[str, ...]
    copy_result: bool = True

    def compile(
        self, static_context: dict[str, JsonObject], _functions: Mapping[str, Function]
    ) -> "Constant | Lookup":
        """Resolve static lookups, copying mutable values; retain runtime lookups.

        Raise ``FieldMappingTemplateConfigError`` if a static path is missing.
        """
        if self.context in static_context:
            value = get_field_value(static_context[self.context], self.path)
            if value is MISSING:
                raise FieldMappingTemplateConfigError(
                    f"Cannot resolve lookup path {self.path!r} "
                    f"in static context root {self.context!r} during constant folding"
                )
            if isinstance(value, (dict, list)):
                value = deepcopy(value)
            return Constant(value)
        return self

    def evaluate(
        self, runtime_context: dict[str, JsonObject], skip_missing_fields: bool = False
    ) -> FieldValue | Missing:
        """Resolve a runtime field and copy mutable values unless borrowing is enabled.

        Missing roots raise ``FieldMappingTemplateLookupError``. Missing fields
        return ``MISSING`` when skipping is enabled, and otherwise raise that error.
        """
        if self.context not in runtime_context:
            raise FieldMappingTemplateLookupError(
                f"Missing runtime context root {self.context!r} for lookup path {self.path!r}"
            )

        value = get_field_value(runtime_context[self.context], self.path)
        if value is MISSING and not skip_missing_fields:
            raise FieldMappingTemplateLookupError(
                f"Cannot resolve lookup path {self.path!r} "
                f"in runtime context root {self.context!r}"
            )
        elif value is MISSING and skip_missing_fields:
            return MISSING

        if self.copy_result and isinstance(value, (dict, list)):
            return deepcopy(value)

        return value


@define(frozen=True)
class ParsedCall:
    """An unresolved function name and arguments produced by parsing.

    Validation checks its name and signature; compilation replaces it with a
    ``Call`` or a folded ``Constant``.
    """

    name: str
    args: tuple["Operation", ...]
    kwargs: Mapping[str, "Operation"]

    def compile(
        self, static_context: dict[str, JsonObject], functions: Mapping[str, Function]
    ) -> "Call | Constant":
        """Prepare a validated call and apply its argument borrowing policy.

        Fold calls only when the function opts in and all arguments are constant.
        Exceptions from functions executed during folding propagate unchanged.
        """
        function = functions[self.name]

        compiled_args: list[Operation] = []
        compiled_kwargs: dict[str, Operation] = {}

        for arg in self.args:
            compiled_arg = arg.compile(static_context, functions)

            if isinstance(compiled_arg, Lookup):
                compiled_arg = Lookup(
                    context=compiled_arg.context,
                    path=compiled_arg.path,
                    copy_result=not function.can_borrow_input,
                )

            compiled_args.append(compiled_arg)

        for key, kwarg in self.kwargs.items():
            compiled_kwarg = kwarg.compile(static_context, functions)

            if isinstance(compiled_kwarg, Lookup):
                compiled_kwarg = Lookup(
                    context=compiled_kwarg.context,
                    path=compiled_kwarg.path,
                    copy_result=not function.can_borrow_input,
                )

            compiled_kwargs[key] = compiled_kwarg

        if function.foldable:
            arg_values = [arg.value for arg in compiled_args if isinstance(arg, Constant)]
            kwarg_values = {
                key: arg.value for key, arg in compiled_kwargs.items() if isinstance(arg, Constant)
            }

            if len(arg_values) == len(compiled_args) and len(kwarg_values) == len(compiled_kwargs):
                return Constant(function.fn(*arg_values, **kwarg_values))

        return Call(function, tuple(compiled_args), compiled_kwargs)

    def evaluate(
        self, _runtime_context: dict[str, JsonObject], _skip_missing_fields: bool = False
    ) -> FieldValue:
        """Raise ``RuntimeError`` because unresolved calls must be compiled first."""
        raise RuntimeError(
            f"Internal error: unresolved ParsedCall {self.name!r} encountered during evaluation; "
            "compile the operation before evaluating"
        )


@define(frozen=True)
class Call:
    """A resolved function and compiled arguments ready for evaluation."""

    function: Function
    args: tuple["Operation", ...]
    kwargs: Mapping[str, "Operation"]

    def compile(
        self, _static_context: dict[str, JsonObject], _functions: Mapping[str, Function]
    ) -> "Operation":
        """Raise ``RuntimeError`` because resolved calls must not be compiled again."""
        raise RuntimeError(
            "Internal error: resolved Call encountered during compilation; expected ParsedCall"
        )

    def evaluate(
        self, runtime_context: dict[str, JsonObject], skip_missing_fields: bool = False
    ) -> FieldValue | Missing:
        """Evaluate positional arguments, then kwargs, and invoke the function.

        A missing argument returns ``MISSING`` without invoking the function.
        Exceptions raised by the function propagate unchanged.
        """
        args = []
        kwargs = {}

        for arg in self.args:
            evaluated_arg = arg.evaluate(runtime_context, skip_missing_fields)
            if evaluated_arg is MISSING:
                return MISSING

            args.append(evaluated_arg)

        for kwarg_key, kwarg_value in self.kwargs.items():
            evaluated_kwarg = kwarg_value.evaluate(runtime_context, skip_missing_fields)

            if evaluated_kwarg is MISSING:
                return MISSING

            kwargs[kwarg_key] = evaluated_kwarg
        return self.function.fn(*args, **kwargs)


@define(frozen=True)
class MappingOperation:
    """Build a dictionary from evaluated key and value operations."""

    entries: tuple[tuple["KeyPath | Operation", "Operation"], ...]
    generated_paths: frozenset[ReadonlyList[str]] = field(factory=frozenset)

    def compile(
        self, static_context: dict[str, JsonObject], functions: Mapping[str, Function]
    ) -> "Constant | MappingOperation":
        """Compile entries, combine known path prefixes and fold static branches.

        Constant template keys become paths, respecting backslash-escaped dots.
        Dynamic keys remain operations. Duplicate or overlapping known paths
        raise ``FieldMappingTemplateConfigError``, regardless of value types.
        Numeric names are allowed only as standalone keys, not as path segments.
        """
        entries = self._compile_entries(static_context, functions)
        return self._prepare_entries(entries)

    @classmethod
    def _prepare_entries(
        cls,
        entries: list[tuple["KeyPath | Operation", "Operation"]],
        *,
        prefix: ReadonlyList[str] = (),
    ) -> "Constant | MappingOperation":
        """Group known path segments recursively, rejecting overlapping destinations."""
        groups: dict[str, list[tuple[ReadonlyList[str], Operation]]] = {}

        for key, value in entries:
            if isinstance(key, KeyPath):
                name = key.segments[0]
                remaining = key.segments[1:]
                groups.setdefault(name, []).append((remaining, value))

        prepared_entries: list[tuple[Operation, Operation]] = []
        emitted_names: set[str] = set()

        # Preserve generated prefixes even when their children fold into constants.
        generated_paths = frozenset(
            key.segments[:length]
            for key, _ in entries
            if isinstance(key, KeyPath)
            for length in range(1, len(key.segments))
        )

        for key, value in entries:
            if not isinstance(key, KeyPath):
                prepared_entries.append((key, value))
                continue

            name = key.segments[0]
            if name in emitted_names:
                continue

            emitted_names.add(name)
            group = groups[name]
            full_path = (*prefix, name)

            direct_values = [child_value for remaining, child_value in group if not remaining]

            prepared_value: Operation
            if direct_values:
                # An explicit assignment owns its entire path.
                if len(group) != 1:
                    raise FieldMappingTemplateConfigError(f"Conflicting mapping path {full_path!r}")

                prepared_value = direct_values[0]
            else:
                child_entries: list[tuple[KeyPath | Operation, Operation]] = [
                    (KeyPath(remaining), child_value) for remaining, child_value in group
                ]
                prepared_value = cls._prepare_entries(child_entries, prefix=full_path)

            prepared_entries.append((Constant(name), prepared_value))

        return cls._fold_entries(prepared_entries, generated_paths=generated_paths)

    @classmethod
    def _fold_entries(
        cls,
        entries: list[tuple["Operation", "Operation"]],
        *,
        generated_paths: frozenset[ReadonlyList[str]],
    ) -> "Constant | MappingOperation":
        """Fold a mapping only when every prepared key and value is constant."""
        constant_values: JsonObject = {}

        for key, value in entries:
            if not isinstance(key, Constant) or not isinstance(value, Constant):
                return cls(entries=tuple(entries), generated_paths=generated_paths)

            if not isinstance(key.value, str):
                raise RuntimeError("Internal error: prepared mapping key must be a string")

            constant_values[key.value] = value.value

        return Constant(constant_values)

    def _compile_entries(
        self, static_context: dict[str, JsonObject], functions: Mapping[str, Function]
    ) -> list[tuple["KeyPath | Operation", "Operation"]]:
        """Compile keys and values, converting constant string keys to parsed paths."""
        compiled_mapping_entries: list[tuple[Operation | KeyPath, Operation]] = []

        for key, value in self.entries:
            compiled_key: KeyPath | Operation
            if not isinstance(key, KeyPath):
                compiled_key = key.compile(static_context, functions)
            else:
                compiled_key = key

            if isinstance(compiled_key, Constant) and not isinstance(compiled_key.value, str):
                raise FieldMappingTemplateConfigError(
                    f"Mapping keys must resolve to strings, got {type(compiled_key.value).__name__}"
                )
            elif isinstance(compiled_key, Constant):
                assert isinstance(compiled_key.value, str)
                compiled_key = KeyPath(tuple(get_dotted_field_list(compiled_key.value)))

            if isinstance(compiled_key, KeyPath) and (
                any(segment.isnumeric() for segment in compiled_key.segments[1:])
                or (compiled_key.segments[0].isnumeric() and len(compiled_key.segments) > 1)
            ):
                raise FieldMappingTemplateConfigError(
                    "Numeric mapping path segment is not supported in a multi-segment path: "
                    f"{compiled_key.segments!r}; use an explicit nested mapping instead"
                )

            compiled_mapping_entries.append(
                (
                    compiled_key,
                    value.compile(static_context, functions),
                )
            )

        return compiled_mapping_entries

    def evaluate(
        self, runtime_context: dict[str, JsonObject], skip_missing_fields: bool = False
    ) -> FieldValue:
        """Build a fresh mapping, expanding runtime paths and skipping missing values.

        Only generated containers may be shared. Non-string keys, numeric names
        in multi-segment paths and conflicting destinations raise
        ``FieldMappingTemplateEvaluationError``.
        """
        result: JsonObject = {}
        # Explicit dictionary values are never registered as shared containers.
        containers: set[ReadonlyList[str]] = set()

        for key_op, value_op in self.entries:
            if isinstance(key_op, KeyPath):
                raise RuntimeError(
                    "Internal error: uncompiled key path encountered during evaluation"
                )

            key = key_op.evaluate(runtime_context, skip_missing_fields)
            if not isinstance(key, str):
                raise FieldMappingTemplateEvaluationError(
                    f"Mapping keys must resolve to strings, got {type(key).__name__}"
                )

            path: ReadonlyList[str]
            if isinstance(key_op, Constant):
                # Compiled names are already parsed, preserve literal dots.
                path = (key,)
            else:
                path = tuple(get_dotted_field_list(key))

                if len(path) > 1 and any(segment.isnumeric() for segment in path):
                    raise FieldMappingTemplateEvaluationError(
                        f"Numeric mapping path segment is not supported "
                        f"in a multi-segment path: {path!r}"
                    )

            value = value_op.evaluate(runtime_context, skip_missing_fields)
            if value is MISSING:
                continue

            self._insert_value(
                result,
                containers,
                path,
                value,
                generated=isinstance(key_op, Constant) and path in self.generated_paths,
            )

        return result

    def _insert_value(
        self,
        result: JsonObject,
        containers: set[ReadonlyList[str]],
        path: ReadonlyList[str],
        value: FieldValue,
        *,
        generated: bool,
    ) -> None:
        """Insert values through generated containers without merging explicit mappings."""
        pending: list[tuple[ReadonlyList[str], FieldValue, bool]] = [
            (
                path,
                value,
                generated,
            )
        ]

        while pending:
            destination, value, generated = pending.pop()
            target = result

            # Generated branches open their destination, values stop at the parent.
            container_path = destination if generated else destination[:-1]

            for length, segment in enumerate(container_path, start=1):
                prefix = destination[:length]

                if segment not in target:
                    target[segment] = {}
                    containers.add(prefix)
                elif prefix not in containers:
                    raise FieldMappingTemplateEvaluationError(
                        f"Duplicate resolved mapping key or conflicting path " f"{destination!r}"
                    )

                child = target[segment]
                if not isinstance(child, dict):
                    raise RuntimeError("Internal error: generated container must be a mapping")
                target = child

            name = destination[-1]

            if generated:
                if not isinstance(value, dict):
                    raise RuntimeError("Internal error: generated branch must contain a mapping")

                # The stack pops last first, so reverse to preserve field order.
                for child_name, child_value in reversed(tuple(value.items())):
                    child_path = (*destination, child_name)
                    pending.append(
                        (
                            child_path,
                            child_value,
                            child_path in self.generated_paths,
                        )
                    )
            else:
                name = destination[-1]
                if name in target:
                    raise FieldMappingTemplateEvaluationError(
                        f"Duplicate resolved mapping key or conflicting path " f"{destination!r}"
                    )

                target[name] = value


@define(frozen=True)
class ListOperation:
    """Build a list by evaluating its entries in order."""

    entries: tuple["Operation", ...]

    def compile(
        self, static_context: dict[str, JsonObject], functions: Mapping[str, Function]
    ) -> "Constant | ListOperation":
        """Compile each element and fold the list when every element is constant."""
        compiled_list_entries: list[Operation] = []
        for list_entry in self.entries:
            compiled_list_entries.append(list_entry.compile(static_context, functions))

        constant_values = [
            entry.value for entry in compiled_list_entries if isinstance(entry, Constant)
        ]

        if len(constant_values) == len(compiled_list_entries):
            return Constant(constant_values)

        return ListOperation(tuple(compiled_list_entries))

    def evaluate(
        self, runtime_context: dict[str, JsonObject], skip_missing_fields: bool = False
    ) -> FieldValue | Missing:
        """Build a fresh list, returning ``MISSING`` if any element is missing."""
        res: list[FieldValue] = []
        for child in self.entries:
            list_entry = child.evaluate(runtime_context, skip_missing_fields)
            if list_entry is MISSING:
                return MISSING
            res.append(list_entry)
        return res


Operation: TypeAlias = Constant | Lookup | ParsedCall | Call | MappingOperation | ListOperation


@define(frozen=True)
class KeyPath:
    """A mapping key whose path separators have already been parsed."""

    segments: ReadonlyList[str]


class Parser:
    """Parse scanned tokens using a shared cursor and explicit whitespace rules.

    Reads beyond EOF and invalid syntax raise ``FieldMappingTemplateConfigError``.
    Parsing builds unresolved calls without invoking or resolving functions.
    """

    def __init__(self, tokens: tuple[Token, ...]) -> None:
        """Start a parser at the beginning of the supplied token tuple."""
        self.tokens = tokens
        self.index = 0

    def _check_eof(self) -> None:
        if self.index >= len(self.tokens):
            raise FieldMappingTemplateConfigError("Unexpected end of template")

    def peek(self) -> Token:
        """Return the current token without consuming it or skipping whitespace."""
        self._check_eof()
        return self.tokens[self.index]

    def advance(self) -> Token:
        """Consume and return exactly one token, including whitespace tokens."""
        self._check_eof()
        token = self.tokens[self.index]
        self.index += 1
        return token

    def expect(self, kind: TokenKind) -> Token:
        """Consume the required kind, raising a configuration error on mismatch."""
        self._check_eof()

        if self.tokens[self.index].kind != kind:
            token = self.tokens[self.index]
            raise FieldMappingTemplateConfigError(
                f"Expected {kind.name}, got {token.kind.name} ({token.value!r})",
                position=token.position,
            )

        return self.advance()

    def skip_whitespace(self) -> None:
        """Consume whitespace only; reaching EOF is allowed."""
        while self.index < len(self.tokens) and self.peek().kind is TokenKind.WHITESPACE:
            self.advance()

    def token_at(self, index: int) -> Token:
        """Read an absolute token index without changing the parser cursor."""
        if index >= len(self.tokens):
            raise FieldMappingTemplateConfigError("Unexpected end of template during lookahead")
        return self.tokens[index]

    def is_sequence(self, kinds: tuple[TokenKind, ...], allow_whitespace: bool = True) -> bool:
        """Check kinds at the cursor without consuming tokens.

        Optionally ignore whitespace before and between matched tokens. Empty
        sequences match; incomplete sequences at EOF do not.
        """
        if len(kinds) == 0:
            return True

        index = self.index
        kind_index = 0
        while True:
            if index >= len(self.tokens):
                return False

            if allow_whitespace and self.token_at(index).kind is TokenKind.WHITESPACE:
                index += 1
                continue

            if self.token_at(index).kind is not kinds[kind_index]:
                return False

            index += 1
            kind_index += 1

            if kind_index >= len(kinds):
                return True

    def parse_key(self) -> KeyPath | Operation:
        """Parse a literal dotted key path or a whole-value template expression.

        Tokens must come from a lexer in key mode. Escaped dots remain inside
        their segment. Mixing literal path segments with expressions is rejected.
        """
        if self.index < len(self.tokens) and self.peek().kind is TokenKind.EXPRESSION_START:
            return self.parse_template()

        path_segments: list[str] = [""]

        while self.index < len(self.tokens):
            token = self.advance()

            match token.kind:
                case TokenKind.TEXT:
                    path_segments[-1] += token.value
                case TokenKind.DOT:
                    path_segments.append("")
                case _:

                    raise FieldMappingTemplateConfigError(
                        f"Unexpected token {token.value!r} in mapping key; "
                        "expected literal text or a dot",
                        position=token.position,
                    )
        return KeyPath(tuple(path_segments))

    def parse_lookup(self, context: str) -> Lookup:
        """Read one or more adjacent ``.field`` segments after a consumed root.

        Leave the first non-path token unread. Whitespace around dots is rejected.
        """
        path: list[str] = []

        while self.peek().kind is TokenKind.DOT:
            self.advance()
            segment = self.expect(TokenKind.TEXT)
            path.append(segment.value)

        if not path:
            token = self.peek()
            raise FieldMappingTemplateConfigError(
                f"Expected at least one field name after context root {context!r}; "
                f"got {token.value!r}",
                position=token.position,
            )

        return Lookup(context=context, path=tuple(path))

    def parse_value(self) -> Operation:
        """Read a literal, lookup or call after optional leading whitespace.

        Function names must immediately precede their opening parenthesis.
        """
        self.skip_whitespace()
        token = self.advance()

        match token.kind:
            case TokenKind.STRING:
                return Constant(token.value)
            case TokenKind.INTEGER:
                return Constant(int(token.value))
            case TokenKind.FLOAT:
                return Constant(float(token.value))
            case TokenKind.BOOLEAN:
                return Constant(token.value in _TRUE_VALUE_STRINGS)
            case TokenKind.NONE:
                return Constant(None)
            case TokenKind.TEXT:
                name = token.value

                if self.peek().kind is TokenKind.LEFT_PAREN:
                    args, kwargs = self.parse_arguments()
                    return ParsedCall(name=name, args=args, kwargs=kwargs)
                return self.parse_lookup(context=name)
            case _:
                raise FieldMappingTemplateConfigError(
                    "Expected a literal, lookup or function call, "
                    f"got {token.kind.name} ({token.value!r})",
                    position=token.position,
                )

    def parse_expression(self) -> Operation:
        """Read a value and left-associative pipes, leaving its delimiter unread.

        Each pipe prepends the preceding value to the next call's positional
        arguments. A pipe function with no explicit arguments may omit ``()``.
        """
        operation = self.parse_value()

        self.skip_whitespace()
        while self.peek().kind is TokenKind.PIPE:
            self.expect(TokenKind.PIPE)
            self.skip_whitespace()
            name = self.expect(TokenKind.TEXT).value

            if self.peek().kind is TokenKind.LEFT_PAREN:
                args, kwargs = self.parse_arguments()
            else:
                args, kwargs = (), {}

            operation = ParsedCall(
                name=name,
                args=(operation, *args),
                kwargs=kwargs,
            )

            self.skip_whitespace()

        return operation

    def parse_arguments(self) -> tuple[tuple[Operation, ...], Mapping[str, Operation]]:
        """Consume parentheses enclosing positional arguments and kwargs.

        Arguments are expressions and may contain calls or pipes. Positional
        arguments must precede unique identifier-named kwargs. Empty calls are
        allowed; trailing commas are rejected.
        """
        self.expect(TokenKind.LEFT_PAREN)
        self.skip_whitespace()

        args: list[Operation] = []
        kwargs: dict[str, Operation] = {}

        if self.peek().kind is TokenKind.RIGHT_PAREN:
            self.advance()
            return tuple(args), kwargs

        while True:
            if self.is_sequence((TokenKind.TEXT, TokenKind.EQUALS)):
                keyword_token = self.advance()
                keyword_name = keyword_token.value
                self.skip_whitespace()
                self.expect(TokenKind.EQUALS)

                if keyword_name in kwargs:
                    raise FieldMappingTemplateConfigError(
                        f"Duplicate keyword argument {keyword_name!r}",
                        position=keyword_token.position,
                    )

                if not keyword_name.isidentifier():
                    raise FieldMappingTemplateConfigError(
                        f"Invalid keyword argument name {keyword_name!r}",
                        position=keyword_token.position,
                    )

                kwargs[keyword_name] = self.parse_expression()
            else:
                if len(kwargs) > 0:
                    token = self.peek()
                    raise FieldMappingTemplateConfigError(
                        "Positional arguments must precede keyword arguments; "
                        f"got {token.value!r}",
                        position=token.position,
                    )

                args.append(self.parse_expression())

            self.skip_whitespace()
            if self.peek().kind is TokenKind.RIGHT_PAREN:
                self.advance()
                return tuple(args), kwargs

            self.expect(TokenKind.COMMA)
            self.skip_whitespace()

    def parse_template(self) -> Operation:
        """Read literal text or a complete ``${ expression }`` and require EOF.

        Empty input becomes an empty string. Text interpolation is unsupported.
        """
        if len(self.tokens) <= 0:
            return Constant("")

        if self.peek().kind is TokenKind.TEXT:
            text = self.advance().value
            if self.index < len(self.tokens):
                token = self.peek()
                raise FieldMappingTemplateConfigError(
                    f"Unexpected token {token.value!r} "
                    "after literal text; interpolation is not supported",
                    position=token.position,
                )

            return Constant(text)

        self.skip_whitespace()
        if self.peek().kind is TokenKind.EXPRESSION_START:
            self.expect(TokenKind.EXPRESSION_START)
            self.skip_whitespace()

            token = self.peek()
            if token.kind is not TokenKind.TEXT:
                raise FieldMappingTemplateConfigError(
                    "Expected a lookup or function call, "
                    f"got {token.kind.name} ({token.value!r})",
                    position=token.position,
                )

            operation = self.parse_expression()
            self.skip_whitespace()
            self.expect(TokenKind.EXPRESSION_END)

            if self.index < len(self.tokens):
                token = self.peek()
                raise FieldMappingTemplateConfigError(
                    f"Unexpected token {token.value!r} after the expression",
                    position=token.position,
                )
            return operation

        token = self.peek()
        raise FieldMappingTemplateConfigError(
            f"Expected literal text or {_EXPRESSION_START!r}, got {token.value!r}",
            position=token.position,
        )


def _parse_recursive(value: FieldValue) -> Operation:
    """Build operations recursively from mappings, lists and scalar values.

    String values and mapping keys are scanned and parsed as templates.
    Integers, booleans, floats and ``None`` become constants.

    Raises
    ------
    FieldMappingTemplateConfigError
        If a value has an unsupported type, a mapping key is not a string, or a
        string contains an invalid template.
    """
    match value:
        case str():
            tokens = Lexer(value).scan()
            operation = Parser(tokens).parse_template()
            return operation
        case int() | float() | bool() | None:
            return Constant(value)
        case Mapping():
            mapping_operations: list[tuple[Operation | KeyPath, Operation]] = []
            for k, v in value.items():
                if not isinstance(k, str):
                    raise FieldMappingTemplateConfigError(
                        f"Mapping keys must be strings, got {type(k).__name__}"
                    )
                key = Parser(Lexer(k, key_mode=True).scan()).parse_key()
                mapping_operations.append((key, _parse_recursive(v)))
            return MappingOperation(entries=tuple(mapping_operations))
        case list():
            return ListOperation(tuple(_parse_recursive(v) for v in value))
        case _:
            assert_never(value)


def _validate_operation(
    op: Operation,
    static_context: dict[str, dict[str, FieldValue]],
    runtime_roots: Collection[str],
    functions: Mapping[str, Function],
) -> None:
    """Check lookup paths, function names and signatures in a parsed tree.

    Runtime field existence is deferred until evaluation. Static values containing
    ``None`` are valid; only missing paths fail validation. Callers must check that
    static and runtime roots do not overlap before calling this function.

    Raises
    ------
    FieldMappingTemplateConfigError
        If a lookup references an undeclared root or an unresolved static path,
        or a call references an unknown function or cannot bind its arguments.
    RuntimeError
        If an already compiled ``Call`` reaches this phase.

    Registered callables must support ``inspect.signature``. This phase never
    invokes them and does not check argument or result value types.
    """
    match op:
        case Constant():
            return
        case Lookup():
            if op.context not in static_context and op.context not in runtime_roots:
                raise FieldMappingTemplateConfigError(
                    f"Unknown context root {op.context!r} for lookup path {op.path!r}; "
                    "the root must be declared in static_context or runtime_roots"
                )

            if op.context in runtime_roots:
                return

            if get_field_value(static_context[op.context], op.path) is MISSING:
                raise FieldMappingTemplateConfigError(
                    f"Cannot resolve lookup path {op.path!r} "
                    f"in static context root {op.context!r}"
                )

            return
        case ParsedCall():
            if op.name not in functions:
                raise FieldMappingTemplateConfigError(f"Unknown function {op.name!r}")

            function = functions[op.name]

            # Cache this on function, not relevant for now
            sig = inspect.signature(function.fn)
            try:
                sig.bind(*op.args, **op.kwargs)
            except TypeError as error:
                raise FieldMappingTemplateConfigError(
                    f"Invalid arguments for function {op.name!r}: {error}"
                ) from error

            for arg in op.args:
                _validate_operation(arg, static_context, runtime_roots, functions)

            for kwarg in op.kwargs.values():
                _validate_operation(kwarg, static_context, runtime_roots, functions)
            return

        case MappingOperation():
            for key, value in op.entries:
                if not isinstance(key, KeyPath):
                    _validate_operation(key, static_context, runtime_roots, functions)
                _validate_operation(value, static_context, runtime_roots, functions)
        case ListOperation():
            for operation in op.entries:
                _validate_operation(operation, static_context, runtime_roots, functions)
        case Call():
            raise RuntimeError(
                "Internal error: resolved Call encountered during validation; expected ParsedCall"
            )
        case _:
            assert_never(op)


@define(frozen=True)
class FieldMappingTemplate:
    """A reusable mapping template prepared with ``compile`` and run with ``evaluate``.

    References use dotted context paths, such as ``${source_event.@timestamp}``
    and ``${rule.description}``. Functions accept positional arguments and kwargs,
    including nested calls: ``${str(source_event.id)}``. A pipe supplies the
    preceding value as the first positional argument: ``${source_event.id | str}``.
    Pipes chain left to right; ``${source_event.id | add(20) | str}`` means
    ``str(add(source_event.id, 20))`` when both functions are registered.

    Default functions are ``str``, ``int``, ``float``, ``lower``, ``upper``,
    ``strip``, ``join``, and ``concat``. ``str`` accepts any field value, including
    mappings, lists, and ``None``. ``int`` and ``float`` use Python conversion
    rules. ``lower``, ``upper``, and ``strip`` operate on strings. ``join`` takes
    a sequence of strings followed by a separator,
    and ``concat`` takes any number of string arguments. Conversion and type
    errors propagate from these functions, during compilation if folded or
    during evaluation otherwise.

    Passing ``functions`` to ``compile`` supplies the complete registry instead.
    Standalone calls require parentheses;
    pipe calls with no explicit arguments can omit them. A function name must
    immediately precede ``(``. Keyword names are identifiers, duplicates are
    invalid, and positional arguments must precede kwargs. Trailing commas are
    unsupported.

    Function arguments support single- and double-quoted strings, signed decimal
    integers and floats (including scientific notation and digit separators),
    ``true``, ``false`` and ``none``. Title-case boolean and none spellings are
    also accepted. Bare literals such as ``${24}`` or ``${"hello"}`` are not
    template expressions. Numeric path segments, such as ``source_event.items.0``,
    remain lookup segments. Backslash escapes the following character, including
    inside quoted strings; it does not translate sequences such as ``\\n`` into
    control characters. Literal text and whole-value expressions are supported;
    interpolation is not supported.

    Mapping keys use the same template syntax as string values, including in
    nested mappings and mappings inside lists. Keys must resolve to strings;
    use an explicit conversion such as ``${source_event.id | str}`` for other
    types. Literal dotted keys and keys resolved from expressions create nested
    mappings: ``{"event.test": "test"}`` produces ``{"event": {"test": "test"}}``.
    Shared path prefixes are combined, and fully static branches are folded.
    Numeric names are allowed as standalone mapping keys, including in explicit
    nested mappings. Multi-segment output paths containing numeric names, such
    as ``event.0`` or ``0.test``, are rejected even when the number is escaped.
    Escape a dot with a backslash to keep it within a literal field name; escape
    the dollar sign to use expression syntax as literal key text. Resolved
    strings are not parsed again as templates. Runtime paths may share generated
    containers, but cannot descend into or overwrite explicitly assigned values.

    Static non-string keys and duplicate or overlapping known paths fail during
    compilation, including when values require runtime evaluation. For example,
    ``event`` and ``event.test`` conflict even if ``event`` contains a mapping.
    Runtime non-string keys, numeric names in multi-segment paths and conflicting
    destinations fail during evaluation.

    For example, ``{"${source_event.name}": "${source_event.value}"}`` evaluated
    with ``{"source_event": {"name": "status", "value": 200}}`` produces
    ``{"status": 200}``.
    """

    root_operation: Operation

    @classmethod
    def compile(
        cls,
        mapping: JsonObject,
        *,
        static_context: dict[str, JsonObject],
        runtime_roots: Collection[str],
        functions: Mapping[str, Function] | None = None,
    ) -> "FieldMappingTemplate":
        """Validate and prepare a mapping, folding expressions known at configuration time.

        Parameters
        ----------
        mapping : dict[str, FieldValue]
            Template configuration containing JSON-compatible values. Nested
            dictionaries and lists are supported. String values and mapping
            keys can contain whole-value expressions; keys must resolve to strings.
        static_context : dict[str, JsonObject]
            Named context roots whose paths are validated and resolved now.
            Resolved dictionaries and lists are deep-copied, so subsequent changes
            to this context do not affect the compiled template.
        runtime_roots : Collection[str]
            Names of roots supplied during evaluation. Their fields are checked
            only when evaluated. Names must not overlap with static roots.
        functions : Mapping[str, Function] | None
            Complete function registry, replacing ``DEFAULT_FUNCTIONS`` when
            supplied. An empty mapping disables all functions. Callables
            must expose inspectable signatures and return ``FieldValue`` values.
            Functions opting into folding may execute during compilation;
            others execute on every evaluation, even with constant arguments.

        Returns
        -------
        FieldMappingTemplate
            A prepared template that can be evaluated repeatedly.

        Raises
        ------
        FieldMappingTemplateConfigError
            If the configuration, root declarations, static references or function
            calls are invalid, a static key resolves to a non-string value, or
            known mapping paths duplicate or overlap one another.

        Exceptions from signature introspection and functions executed during
        folding propagate unchanged.
        """
        if functions is None:
            functions = DEFAULT_FUNCTIONS

        overlapping_roots = static_context.keys() & set(runtime_roots)
        if overlapping_roots:
            raise FieldMappingTemplateConfigError(
                "Context roots must not be declared as both static and runtime; "
                f"overlapping roots: {sorted(overlapping_roots)!r}"
            )

        root_operation = _parse_recursive(mapping)

        if not isinstance(root_operation, MappingOperation):
            raise FieldMappingTemplateConfigError(
                f"Template root must be a mapping, got {type(mapping).__name__!r}"
            )

        _validate_operation(root_operation, static_context, runtime_roots, functions)

        compiled_root = root_operation.compile(static_context, functions)

        return cls(compiled_root)

    def evaluate(
        self,
        *,
        runtime_context: dict[str, dict[str, FieldValue]],
        skip_missing_fields: bool = False,
    ) -> dict[str, FieldValue]:
        """Resolve the compiled template against runtime context and return its mapping.

        Parameters
        ----------
        runtime_context : dict[str, dict[str, FieldValue]]
            Named runtime roots. Each root referenced by the template must be
            present and contain the requested fields; explicit ``None`` is valid.
        skip_missing_fields : bool
            If true, omit mapping entries whose values depend on a missing field.
            A missing function argument skips the call; a missing list element
            skips the whole list rather than changing its length. Nested mappings
            can remain empty after omissions. Missing roots still raise a lookup
            error, and missing mapping keys fail the string-key check. Defaults
            to false, which raises a lookup error for any missing field.

        Returns
        -------
        dict[str, FieldValue]
            A fresh result mapping. Mutable constants and direct runtime lookup
            values are deep-copied on every call, including nested dictionaries
            and lists. Runtime functions may borrow lookup values if they
            neither mutate nor retain or return mutable input references.
            Changing the result does not change the source context, and
            evaluation itself does not modify the supplied context.

        Raises
        ------
        FieldMappingTemplateLookupError
            If a runtime root is missing or a field is missing while
            ``skip_missing_fields`` is false.
        FieldMappingTemplateEvaluationError
            If a key resolves to a non-string value, a runtime multi-segment path
            contains a numeric name, or resolved paths collide or overlap.
        TypeError
            If the compiled root does not produce a dictionary.

        Exceptions from runtime functions propagate unchanged. Function result
        types are the responsibility of registered implementations.
        """
        result = self.root_operation.evaluate(runtime_context, skip_missing_fields)

        if not isinstance(result, dict):
            raise TypeError("Compiled template root did not produce a mapping")

        return result
