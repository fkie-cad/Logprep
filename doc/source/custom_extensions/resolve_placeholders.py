"""
Resolve Placeholders
====================

Sphinx extension which resolves context dependent placeholders sourced from pydoc.

This extension allows for referencing user-facing classes (like processors) without
sacrificing reusability through inheritance in other components.

Example
-------

    class Config(...):

        list_file_paths: list[str] = field(...)
        \"\"\"
        List of files. For string format see :ref:`getters`.

        .. security-best-practice::
           :title: |PROCESSOR| - list file paths Memory Consumption

           ...
        \"\"\"


Rendered below :code:`ListComparisonRule.Config` the title reads
:code:`List Comparison Processor - list file paths Memory Consumption`, rendered below
:code:`NetworkComparisonRule.Config` it reads
:code:`Network Comparison Processor - list file paths Memory Consumption` - from a single
docstring.

Available placeholders
----------------------

Placeholders are resolved from the object path autodoc reports, which has the shape
:code:`logprep.<category>.<key>.<module>.<Class>...`.  Because that path is the one from
the :code:`autoclass` directive, an inherited attribute resolves against the subclass it
is rendered below, not the class that defines it.

For the component's category (:code:`processor` / :code:`connector`) and the documented
class's role (:code:`rule` / :code:`input` / :code:`output`), three placeholders each are
produced.  Writing ``X`` for the upper case word:

``|X_KEY|``
    The snake case configuration key, e.g. :code:`network_comparison`.

``|X_NAME|``
    The human readable name, e.g. :code:`Network Comparison`.

``|X|``
    The name suffixed with the word, e.g. :code:`|PROCESSOR|` -> :code:`Network Comparison
    Processor`, :code:`|RULE|` -> :code:`Network Comparison Rule`.
"""

from __future__ import annotations

import itertools
import re
import typing
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from docutils.parsers.rst.states import Body
from sphinx.util import logging

if TYPE_CHECKING:
    from sphinx.application import Sphinx

logger = logging.getLogger(__name__)


Category = Literal["processor", "connector"]

Role = Literal["rule", "processor", "input", "output"]

CATEGORIES: tuple[Category, ...] = ("processor", "connector")

ROLE_MODULES: tuple[Role, ...] = ("rule", "processor", "input", "output")

PLACEHOLDER_PATTERN = re.compile(r"\|([A-Z_]+)\|")

DOCUMENTED_TYPES = ("module", "class", "attribute", "property")

HUMANIZE_OVERWRITE = {
    "Opensearch": "OpenSearch",
    "Geoip Enricher": "GeoIP Enricher",
}


class ProcessingError(Exception):
    """Raised if parsing or processing failed"""


@dataclass(frozen=True)
class ComponentMeta:
    """A documented component, parsed from its object path."""

    key: str
    category: Category
    role: Role | None


def parse_component_object_path(name: str) -> ComponentMeta:
    """Parse a component object path or raises a `ProcessingError` on failure.

    The path shape is :code:`logprep[.ng].<category>.<key>.<module>.<Class>...`, so both
    :code:`logprep.processor.network_comparison.rule.NetworkComparisonRule` and
    :code:`logprep.ng.processor.network_comparison.rule.NetworkComparisonRule` parse to
    :code:`ComponentMeta(key="network_comparison", category="processor", role="rule")`.
    """
    try:
        parts = name.removeprefix("logprep.").removeprefix("ng.").split(".")
        category, key, module = parts[:3]
        if category not in CATEGORIES or key == "base":
            # exclude entries like logprep.processor.base
            raise ProcessingError(f"no component in object path: {name}")
        role = module if module in ROLE_MODULES else None
        return ComponentMeta(
            key=key,
            category=typing.cast(Category, category),
            role=typing.cast(Role | None, role),
        )
    except ValueError as error:
        raise ProcessingError(f"no component in object path: {name}") from error


def humanize(snake: str) -> str:
    """Turn a snake_case token into spaced Title Case.

    :code:`network_comparison` -> :code:`Network Comparison`, :code:`s3` -> :code:`S3`.
    """
    result = " ".join(word[:1].upper() + word[1:] for word in snake.split("_"))
    return HUMANIZE_OVERWRITE.get(result, result)


def replacements_for(name: str) -> dict[str, str]:
    """Map every placeholder available for ``name`` to its value.

    For the component's category and the documented class's role, three placeholders are
    produced:

    * :code:`|X_KEY|` - the snake case configuration key, e.g. :code:`network_comparison`;
    * :code:`|X_NAME|` - the human readable name, e.g. :code:`Network Comparison`;
    * :code:`|X|` - the name suffixed with the word, e.g. :code:`Network Comparison
      Processor`, :code:`Network Comparison Rule`.
    """
    meta = parse_component_object_path(name)

    key = meta.key
    readable = humanize(key)

    roles: set[Category | Role] = {meta.category}
    if meta.role is not None:
        roles.add(meta.role)

    result: dict[str, str] = {}
    for role in roles:
        upper = role.upper()
        result[upper] = f"{readable} {humanize(role)}"
        result[f"{upper}_NAME"] = readable
        result[f"{upper}_KEY"] = key
    return result


DOCUTILS_LINE_PATTERN = re.compile(Body.patterns["line"])
"""docutils' own pattern for a section underline, reused so this stays in step with it."""


def is_section_underline(line: str) -> bool:
    """Return whether ``line`` is an RST section underline."""
    return bool(line) and DOCUTILS_LINE_PATTERN.fullmatch(line) is not None


def resolve_placeholders(_, what: str, name: str, __, ___, lines: list[str]) -> None:
    """
    Replace the known placeholders in a docstring with class specific values.

    When a replacement changes a section title, the underline on the following line is
    adapted to the new length so the result conforms to the RST standard.
    """
    if what not in DOCUMENTED_TYPES:
        return
    if not any(PLACEHOLDER_PATTERN.search(line) for line in lines):
        return

    try:
        replacements = replacements_for(name)
    except ProcessingError as error:
        logger.warning("cannot find replacements for name %s (%s)", name, str(error))
        return

    def replace(match: re.Match) -> str:
        placeholder = match.group(1)
        if placeholder not in replacements:
            logger.warning(
                "cannot resolve placeholder |%s| in %s: no class in the object path",
                placeholder,
                name,
            )
            return match.group(0)
        return replacements[placeholder]

    for index, (line, next_line) in enumerate(itertools.zip_longest(lines, lines[1:])):
        resolved = PLACEHOLDER_PATTERN.sub(replace, line)
        lines[index] = resolved
        if resolved == line or next_line is None:
            continue
        if is_section_underline(next_line):
            title_char = next_line[0]
            lines[index + 1] = title_char * len(resolved)


def setup(app: Sphinx) -> dict:
    """Register the extension."""
    app.connect("autodoc-process-docstring", resolve_placeholders)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
