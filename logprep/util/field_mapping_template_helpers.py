from collections.abc import Callable, ItemsView, Mapping, ValuesView
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, TypeAlias

from attr import define, field

from logprep.util.helper import FieldValue, add_fields_to

if TYPE_CHECKING:
    from logprep.processor.base.rule import Rule

ContextEntry: TypeAlias = FieldValue | Callable[[], FieldValue]


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


def concat(*values: str) -> str:
    """Concatenate string arguments without a separator; other types raise ``TypeError``."""
    return "".join(values)


DEFAULT_FUNCTIONS: Final[Mapping[str, Function]] = MappingProxyType(
    {
        "str": Function(lambda x: str(x), can_borrow_input=True, foldable=True),
        "int": Function(lambda x: int(x), can_borrow_input=True, foldable=True),
        "float": Function(lambda x: float(x), can_borrow_input=True, foldable=True),
        "lower": Function(lambda x: str.lower(x), can_borrow_input=True, foldable=True),
        "upper": Function(lambda x: str.upper(x), can_borrow_input=True, foldable=True),
        "strip": Function(lambda x: str.strip(x), can_borrow_input=True, foldable=True),
        "join": Function(
            lambda values, separator: separator.join(values), can_borrow_input=True, foldable=True
        ),
        "concat": Function(concat, can_borrow_input=True, foldable=True),
    }
)


class LazyContext(dict[str, FieldValue]):
    """Expose fixed context keys whose values can be computed on first access.

    ``entries`` maps names to field values or zero-argument factories. Literal
    values are stored immediately. Accessing a factory-backed key through
    ``context[key]`` or ``get`` invokes its factory and caches the returned value
    for this instance, including ``None``. If a factory raises, the exception
    propagates and a later access retries it.

    Membership, length, key iteration, and ``keys()`` include unresolved keys
    without invoking their factories. ``items()`` and ``values()`` resolve values
    as their views are iterated. ``materialize()`` resolves all remaining values
    and returns a plain dictionary; mutable values are shared, not copied.

    For example, ``LazyContext({"id": lambda: str(uuid4())})`` generates an ID
    only when read and returns the same ID on subsequent reads. Create a new
    instance for each evaluation to refresh generated values.

    Use this object through its read methods. Inherited dictionary mutation and
    copying operations are not synchronized with the declared lazy keys; use
    ``materialize()`` to obtain a complete plain dictionary.
    """

    def __init__(self, entries: Mapping[str, ContextEntry]):
        """Register fixed entries and deferred factories without invoking them."""
        super().__init__()

        self._keys = dict.fromkeys(entries)
        self._factories: dict[str, Callable[[], FieldValue]] = {}

        for key, value in entries.items():
            if callable(value):
                self._factories[key] = value
            else:
                dict.__setitem__(self, key, value)

    def __missing__(self, key: str) -> FieldValue:
        factory = self._factories[key]
        value = factory()
        dict.__setitem__(self, key, value)
        del self._factories[key]
        return value

    def __contains__(self, key: object) -> bool:
        return key in self._keys

    def __iter__(self):
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def get(self, key, default=None):
        """Resolve a declared key, or return ``default`` for an unknown key."""
        if key in self:
            return self[key]
        return default

    def keys(self):
        """Return a view of declared keys without computing their values."""
        return self._keys.keys()

    def items(self):
        """Return an items view that resolves lazy values as it is iterated."""
        return ItemsView(self)

    def values(self):
        """Return a values view that resolves lazy values as it is iterated."""
        return ValuesView(self)

    def materialize(self) -> dict[str, FieldValue]:
        """Resolve all keys and return a plain dictionary without copying its values."""
        return {key: self[key] for key in self}


SOURCE_EVENT_CONTEXT: Final[str] = "source_event"


def source_fields_to_fmt(source_fields: list[str]) -> dict[str, FieldValue]:
    """Build a nested template selecting each dotted path from ``source_event``."""
    result: dict[str, FieldValue] = {}
    for field in source_fields:
        fmt = f"${{{SOURCE_EVENT_CONTEXT}.{field}}}"

        add_fields_to(result, {field: fmt})

    return result


def rule_to_fmt_context(rule: "Rule") -> dict[str, FieldValue]:
    """Expose a rule's string ID, description, and normalized filter to templates."""
    return {
        "description": rule.description,
        "id": rule.id,
        "filter": rule.filter_str,
    }
