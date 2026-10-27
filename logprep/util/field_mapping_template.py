"""Compile field mapping templates against static context and evaluate runtime context."""

import inspect
import re
from collections.abc import Callable, Collection, Mapping
from copy import deepcopy
from enum import Enum, auto
from os import path
from types import MappingProxyType
from typing import Final, TypeAlias, TypeVar, assert_never

from attr import field
from attrs import define

from logprep.abc.exceptions import LogprepException
from logprep.util.helper import (
    MISSING,
    FieldValue,
    JsonObject,
    get_field_value,
)

_EXPRESSION_START: Final[str] = "${"
_EXPRESSION_END: Final[str] = "}"
_ESCAPE_CHARACTER: Final[str] = "\\"
_PATH_SEPARATOR: Final[str] = "."
_CONVERSION_SEPARATOR: Final[str] = "|"
_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"[+-]?[0-9](?:_?[0-9])*(?:\.[0-9](?:_?[0-9])*)?(?:[eE][+-]?[0-9]+)?" r"(?=$|[\s(),=|}])"
)

T = TypeVar("T")
ReadonlyList: TypeAlias = tuple[T, ...]


class FieldMappingTemplateConfigError(LogprepException):
    """Invalid field mapping template configuration."""


class FieldMappingTemplateEvaluationError(LogprepException):
    """A compiled field mapping template could not be evaluated."""


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


@define(frozen=True)
class Token:
    """A scanned value with its kind and zero-based source position."""

    kind: TokenKind
    value: str
    position: int


def _scan_quoted_string(template: str, position: int) -> tuple[Token, int]:
    """Read a quoted string, consuming backslash escapes as in template text."""
    start = position
    quote = template[position]
    value: list[str] = []
    position += 1
    while position < len(template):
        character = template[position]
        if character == quote:
            return Token(TokenKind.STRING, "".join(value), start), position + 1
        if character == _ESCAPE_CHARACTER:
            if position + 1 == len(template):
                raise FieldMappingTemplateConfigError(f"Trailing backslash at position {position}")
            position += 1
        value.append(template[position])
        position += 1
    raise FieldMappingTemplateConfigError(f"Unclosed string at position {start}")


def _scan_template(template: str) -> ReadonlyList[Token]:
    """Scan text and expressions, consuming backslash escapes.

    Inside expressions, punctuation and whitespace become separate tokens.
    Quoted strings shield their contents from expression delimiters. At value
    boundaries, decimal numbers (including signs, digit separators and scientific
    notation), booleans and none become literal tokens. Numeric path segments
    remain text. Escaped characters remain text, including escaped whitespace.
    Token values remain strings; quoted values omit their surrounding quotes.
    Positions are zero-based offsets in the original template, including the
    opening quote or sign for literals.

    This only scans: expression grammar and context validation belong to the
    parser and compiler.

    Raises
    ------
    FieldMappingTemplateConfigError
        If an escape is incomplete, a string is unclosed, or an expression is
        nested or unclosed.
    """
    # Keep escape handling and expression transitions together in the scanning loop.
    # pylint: disable=too-many-branches,too-many-statements
    tokens: list[Token] = []
    text: list[str] = []
    text_start = 0
    text_escaped = False
    expression_start: int | None = None
    position = 0

    def at_value_start() -> bool:
        previous = next(
            (token.kind for token in reversed(tokens) if token.kind is not TokenKind.WHITESPACE),
            None,
        )
        return previous in (
            TokenKind.EXPRESSION_START,
            TokenKind.LEFT_PAREN,
            TokenKind.COMMA,
            TokenKind.EQUALS,
        )

    def flush_text() -> None:
        nonlocal text_escaped
        if text:
            value = "".join(text)
            kind = TokenKind.TEXT
            if (
                expression_start is not None
                and not text_escaped
                and at_value_start()
                and (position == len(template) or template[position] != _PATH_SEPARATOR)
            ):
                if value in ("true", "false", "True", "False"):
                    kind = TokenKind.BOOLEAN
                elif value in ("none", "None"):
                    kind = TokenKind.NONE
            tokens.append(Token(kind, value, text_start))
            text.clear()
            text_escaped = False

    while position < len(template):
        character = template[position]

        if character == _ESCAPE_CHARACTER:
            if position + 1 == len(template):
                raise FieldMappingTemplateConfigError(f"Trailing backslash at position {position}")
            if not text:
                text_start = position
            text_escaped = True
            text.append(template[position + 1])
            position += len(_ESCAPE_CHARACTER) + 1
            continue

        if template.startswith(_EXPRESSION_START, position):
            if expression_start is not None:
                raise FieldMappingTemplateConfigError(f"Nested expression at position {position}")
            flush_text()
            tokens.append(Token(TokenKind.EXPRESSION_START, _EXPRESSION_START, position))
            expression_start = position
            position += len(_EXPRESSION_START)
            continue

        if expression_start is not None:
            if character in ("'", '"'):
                flush_text()
                token, position = _scan_quoted_string(template, position)
                tokens.append(token)
                continue

            if not text and at_value_start():
                number = _NUMBER_PATTERN.match(template, position)
                if number is not None:
                    value = number.group()
                    kind = TokenKind.FLOAT if any(c in value for c in ".eE") else TokenKind.INTEGER
                    tokens.append(Token(kind, value, position))
                    position = number.end()
                    continue

            if template.startswith(_EXPRESSION_END, position):
                flush_text()
                tokens.append(Token(TokenKind.EXPRESSION_END, _EXPRESSION_END, position))
                expression_start = None
                position += len(_EXPRESSION_END)
                continue

            delimiter = None
            if character == _PATH_SEPARATOR:
                delimiter = TokenKind.DOT
            elif character == _CONVERSION_SEPARATOR:
                delimiter = TokenKind.PIPE
            elif character == "(":
                delimiter = TokenKind.LEFT_PAREN
            elif character == ")":
                delimiter = TokenKind.RIGHT_PAREN
            elif character == ",":
                delimiter = TokenKind.COMMA
            elif character == "=":
                delimiter = TokenKind.EQUALS
            elif character.isspace():
                delimiter = TokenKind.WHITESPACE

            if delimiter is not None:
                flush_text()
                tokens.append(Token(delimiter, character, position))
                position += 1
                continue

        if not text:
            text_start = position
        text.append(character)
        position += 1

    if expression_start is not None:
        raise FieldMappingTemplateConfigError(f"Unclosed expression at position {expression_start}")

    flush_text()
    return tuple(tokens)


@define(frozen=True)
class Function:
    """A template function returning a ``FieldValue``.

    ``fn`` must expose a signature supported by ``inspect.signature``. Wrap
    built-ins without signature metadata in a Python function before registering
    them. Argument binding checks calling conventions, not argument or result
    types; implementations must honor the ``FieldValue`` result contract.

    ``foldable`` permits execution during compilation when all positional and
    keyword arguments are constant. Only deterministic functions without external
    side effects should opt in. Other functions run on every evaluation.

    ``can_borrow_input`` promises that the function neither mutates nor retains
    nor returns mutable references from any argument, including kwargs. It lets
    direct runtime lookup arguments skip copying. Both options default to false.
    """

    fn: Callable[
        ..., FieldValue
    ]  # We wanted intermediate "object"s but that is actually way harder
    # to validate than we previously thought because type hints mean nothing
    can_borrow_input: bool = field(default=False)
    foldable: bool = field(default=False)


@define(frozen=True)
class Constant:
    """A prepared value; evaluation deep-copies mutable dict/list values."""

    value: FieldValue


@define(frozen=True)
class Lookup:
    """A context root and unescaped field path with a compiled copy policy.

    ``copy_result`` deep-copies runtime dictionaries and lists by default.
    Compilation disables it for arguments of functions that can borrow input.
    """

    context: str
    path: tuple[str, ...]
    copy_result: bool = True


@define(frozen=True)
class ParsedCall:
    """An unresolved function name and arguments produced by parsing.

    Validation checks its name and signature; compilation replaces it with a
    ``Call`` or a folded ``Constant``.
    """

    name: str
    args: tuple["Operation", ...]
    kwargs: Mapping[str, "Operation"]


@define(frozen=True)
class Call:
    """A resolved function and compiled arguments ready for evaluation."""

    function: Function
    args: tuple["Operation", ...]
    kwargs: Mapping[str, "Operation"]


@define(frozen=True)
class MappingOperation:
    """Build a dictionary from evaluated key and value operations."""

    entries: tuple[tuple["Operation", "Operation"], ...]


@define(frozen=True)
class ListOperation:
    """Build a list by evaluating its entries in order."""

    entries: tuple["Operation", ...]


Operation: TypeAlias = Constant | Lookup | ParsedCall | Call | MappingOperation | ListOperation


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
                f"Expected {kind.name} at position {token.position}, "
                f"got {token.kind.name} ({token.value!r})"
            )

        return self.advance()

    def skip_whitespace(self) -> None:
        """Consume whitespace only; reaching EOF is allowed."""
        while self.index < len(self.tokens) and self.peek().kind is TokenKind.WHITESPACE:
            self.advance()

    def lookahead(self, index: int) -> Token:
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

            if allow_whitespace and self.lookahead(index).kind is TokenKind.WHITESPACE:
                index += 1
                continue

            if self.lookahead(index).kind is not kinds[kind_index]:
                return False

            index += 1
            kind_index += 1

            if kind_index >= len(kinds):
                return True

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
                f"got {token.value!r} at position {token.position}"
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
                return Constant(token.value in ("true", "True"))
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
                    f"Expected a literal, lookup or function call at position {token.position}, "
                    f"got {token.kind.name} ({token.value!r})"
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
                        f"Duplicate keyword argument {keyword_name!r} "
                        f"at position {keyword_token.position}"
                    )

                if not keyword_name.isidentifier():
                    raise FieldMappingTemplateConfigError(
                        f"Invalid keyword argument name {keyword_name!r} "
                        f"at position {keyword_token.position}"
                    )

                kwargs[keyword_name] = self.parse_expression()
            else:
                if len(kwargs) > 0:
                    token = self.peek()
                    raise FieldMappingTemplateConfigError(
                        "Positional arguments must precede keyword arguments; "
                        f"got {token.value!r} at position {token.position}"
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
                    f"Unexpected token {token.value!r} at position {token.position} "
                    "after literal text; interpolation is not supported"
                )

            return Constant(text)

        self.skip_whitespace()
        if self.peek().kind is TokenKind.EXPRESSION_START:
            self.expect(TokenKind.EXPRESSION_START)
            self.skip_whitespace()

            token = self.peek()
            if token.kind is not TokenKind.TEXT:
                raise FieldMappingTemplateConfigError(
                    f"Expected a lookup or function call at position {token.position}, "
                    f"got {token.kind.name} ({token.value!r})"
                )

            operation = self.parse_expression()
            self.skip_whitespace()
            self.expect(TokenKind.EXPRESSION_END)

            if self.index < len(self.tokens):
                token = self.peek()
                raise FieldMappingTemplateConfigError(
                    f"Unexpected token {token.value!r} at position {token.position} "
                    "after the expression"
                )
            return operation

        token = self.peek()
        raise FieldMappingTemplateConfigError(
            f"Expected literal text or {_EXPRESSION_START!r} at position {token.position}, "
            f"got {token.value!r}"
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
            tokens = _scan_template(value)
            operation = Parser(tokens).parse_template()
            return operation
        case int() | float() | bool() | None:
            return Constant(value)
        case Mapping():
            mapping_operations: list[tuple[Operation, Operation]] = []
            for k, v in value.items():
                if not isinstance(k, str):
                    raise FieldMappingTemplateConfigError(
                        f"Mapping keys must be strings, got {type(k).__name__}"
                    )
                mapping_operations.append((_parse_recursive(k), _parse_recursive(v)))
            return MappingOperation(entries=tuple(mapping_operations))
        case list():
            return ListOperation(tuple(_parse_recursive(v) for v in value))
        case _:
            assert_never(value)


def _validate_operation(
    op: Operation,
    static_context: dict[str, dict[str, FieldValue]],
    runtime_roots: Collection[str],
    functions: dict[str, Function],
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
            for entry in op.entries:
                _validate_operation(entry[0], static_context, runtime_roots, functions)
                _validate_operation(entry[1], static_context, runtime_roots, functions)
        case ListOperation():
            for operation in op.entries:
                _validate_operation(operation, static_context, runtime_roots, functions)
        case Call():
            raise RuntimeError(
                "Internal error: resolved Call encountered during validation; expected ParsedCall"
            )
        case _:
            assert_never(op)


def _compile_operation(
    op: Operation,
    static_context: dict[str, dict[str, FieldValue]],
    functions: dict[str, Function],
) -> Operation:
    """Resolve functions and fold static operations in a validated parsed tree.

    Static dictionaries and lists are deep-copied when resolved from context.
    Containers become constants when all their children are constant. Runtime
    lookups and operations depending on them remain for evaluation. Runtime
    lookup arguments skip copying only when their function can borrow input;
    static lookup values are copied regardless of the function's capability.
    Calls fold only when their function opts in and all positional and keyword
    arguments compile to constants. Other calls become resolved ``Call`` nodes.

    Raises
    ------
    FieldMappingTemplateConfigError
        If a static path cannot be resolved or a constant key is not a string.
    RuntimeError
        If an already compiled ``Call`` reaches this phase.

    Exceptions from functions executed during folding propagate unchanged.
    """
    # Each operation kind returns its prepared form directly.
    # pylint: disable=too-many-return-statements,too-many-branches
    match op:
        case Constant():
            return op

        case Lookup():
            if op.context in static_context:
                value = get_field_value(static_context[op.context], op.path)
                if value is MISSING:
                    raise FieldMappingTemplateConfigError(
                        f"Cannot resolve lookup path {op.path!r} "
                        f"in static context root {op.context!r} during constant folding"
                    )
                if isinstance(value, (dict, list)):
                    value = deepcopy(value)
                return Constant(value)
            return op

        case ParsedCall():
            function = functions[op.name]

            compiled_args: list[Operation] = []
            compiled_kwargs: dict[str, Operation] = {}

            for arg in op.args:
                compiled_arg = _compile_operation(arg, static_context, functions)

                if isinstance(compiled_arg, Lookup):
                    compiled_arg = Lookup(
                        context=compiled_arg.context,
                        path=compiled_arg.path,
                        copy_result=not function.can_borrow_input,
                    )

                compiled_args.append(compiled_arg)

            for key, kwarg in op.kwargs.items():
                compiled_kwarg = _compile_operation(kwarg, static_context, functions)

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
                    key: arg.value
                    for key, arg in compiled_kwargs.items()
                    if isinstance(arg, Constant)
                }

                if len(arg_values) == len(compiled_args) and len(kwarg_values) == len(
                    compiled_kwargs
                ):
                    return Constant(function.fn(*arg_values, **kwarg_values))

            return Call(function, tuple(compiled_args), compiled_kwargs)

        case MappingOperation():
            compiled_mapping_entries: list[tuple[Operation, Operation]] = []
            for mapping_entry in op.entries:
                compiled_key = _compile_operation(mapping_entry[0], static_context, functions)
                if isinstance(compiled_key, Constant) and not isinstance(compiled_key.value, str):
                    raise FieldMappingTemplateConfigError(
                        f"Mapping keys must resolve to strings, got {type(compiled_key.value).__name__}"
                    )

                compiled_mapping_entries.append(
                    (
                        compiled_key,
                        _compile_operation(mapping_entry[1], static_context, functions),
                    )
                )

            constant_mapping_values: dict[str, FieldValue] = {
                key.value: operation.value
                for key, operation in compiled_mapping_entries
                if isinstance(operation, Constant)
                and isinstance(key, Constant)
                and isinstance(key.value, str)
            }

            if len(constant_mapping_values) == len(compiled_mapping_entries):
                return Constant(constant_mapping_values)

            return MappingOperation(entries=tuple(compiled_mapping_entries))

        case ListOperation():
            compiled_list_entries: list[Operation] = []
            for list_entry in op.entries:
                compiled_list_entries.append(
                    _compile_operation(list_entry, static_context, functions)
                )

            constant_values = [
                entry.value for entry in compiled_list_entries if isinstance(entry, Constant)
            ]

            if len(constant_values) == len(compiled_list_entries):
                return Constant(constant_values)

            return ListOperation(tuple(compiled_list_entries))
        case Call():
            raise RuntimeError(
                "Internal error: resolved Call encountered during compilation; expected ParsedCall"
            )
        case _:
            assert_never(op)


def _evaluate_operation(
    op: Operation, runtime_context: dict[str, dict[str, FieldValue]]
) -> FieldValue:
    """Evaluate a prepared operation tree using the supplied runtime context.

    Constant and runtime lookup dictionaries and lists are deep-copied, except
    runtime arguments of functions that can borrow input. Such functions must
    neither mutate nor retain or return mutable input references. Mapping/list
    operations build fresh containers.

    Raises
    ------
    FieldMappingTemplateEvaluationError
        If a runtime context root or lookup path is missing, a resolved key is
        not a string, or two keys in the same mapping resolve to the same string.
    RuntimeError
        If an unresolved ``ParsedCall`` reaches this phase.

    Positional arguments are evaluated in order, followed by keyword arguments
    in insertion order. Exceptions from functions propagate unchanged.
    """
    match op:
        case Constant():
            if isinstance(op.value, (dict, list)):
                return deepcopy(op.value)
            return op.value

        case Lookup():
            if op.context not in runtime_context:
                raise FieldMappingTemplateEvaluationError(
                    f"Missing runtime context root {op.context!r} " f"for lookup path {op.path!r}"
                )

            value = get_field_value(runtime_context[op.context], op.path)
            if value is MISSING:
                raise FieldMappingTemplateEvaluationError(
                    f"Cannot resolve lookup path {op.path!r} "
                    f"in runtime context root {op.context!r}"
                )

            if op.copy_result and isinstance(value, (dict, list)):
                return deepcopy(value)

            return value

        case Call():
            args = []
            kwargs = {}

            for arg in op.args:
                args.append(_evaluate_operation(arg, runtime_context))

            for kwarg_key, kwarg_value in op.kwargs.items():
                kwargs[kwarg_key] = _evaluate_operation(kwarg_value, runtime_context)

            return op.function.fn(*args, **kwargs)

        case MappingOperation():
            result: JsonObject = {}

            for key_op, value_op in op.entries:
                key = _evaluate_operation(key_op, runtime_context)
                if not isinstance(key, str):
                    raise FieldMappingTemplateEvaluationError(
                        f"Mapping keys must resolve to strings, got {type(key).__name__}"
                    )
                if key in result:
                    raise FieldMappingTemplateEvaluationError(
                        f"Duplicate resolved mapping key {key!r}"
                    )
                result[key] = _evaluate_operation(value_op, runtime_context)

            return result
        case ListOperation():
            return [_evaluate_operation(child, runtime_context) for child in op.entries]
        case ParsedCall():
            raise RuntimeError(
                f"Internal error: unresolved ParsedCall {op.name!r} encountered during evaluation; "
                "compile the operation before evaluating"
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

    Only ``str`` is provided by default. Passing ``functions`` to ``compile``
    supplies the complete registry instead. Standalone calls require parentheses;
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
    types. Resolved keys are literal dictionary keys: dots do not create nested
    mappings, and resolved strings are not parsed again as templates. Escape
    the dollar sign to use expression syntax as literal key text.

    Static non-string keys fail during compilation. Runtime non-string keys
    and duplicate resolved keys within a mapping fail during evaluation.
    This includes duplicate keys whose expressions are entirely static.

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
        functions: dict[str, Function] | None = None,
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
        functions : dict[str, Function] | None
            Complete function registry, replacing the default ``str`` function
            when supplied. An empty mapping disables all functions. Callables
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
            calls are invalid, or a static key resolves to a non-string value.

        Exceptions from signature introspection and functions executed during
        folding propagate unchanged.
        """
        if functions is None:
            functions = {"str": Function(lambda x: str(x), can_borrow_input=True, foldable=True)}

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

        compiled_root = _compile_operation(root_operation, static_context, functions)

        return cls(compiled_root)

    def evaluate(
        self, *, runtime_context: dict[str, dict[str, FieldValue]]
    ) -> dict[str, FieldValue]:
        """Resolve the compiled template against runtime context and return its mapping.

        Parameters
        ----------
        runtime_context : dict[str, dict[str, FieldValue]]
            Named runtime roots. Each root referenced by the template must be
            present and contain the requested fields; explicit ``None`` is valid.

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
        FieldMappingTemplateEvaluationError
            If a runtime root or field path is missing, a key resolves to a
            non-string value, or resolved keys collide within the same mapping.
        TypeError
            If the compiled root does not produce a dictionary.

        Exceptions from runtime functions propagate unchanged. Function result
        types are the responsibility of registered implementations.
        """
        result = _evaluate_operation(self.root_operation, runtime_context)

        if not isinstance(result, dict):
            raise TypeError("Compiled template root did not produce a mapping")

        return result
