"""
Init-Field Class Filter
=======================

This extension filters attrs-based classes for fields with `init=False` and hides those.
Those fields are either only used internally or explicitly disabled.
"""

from typing import Any

import attrs
from sphinx.application import Sphinx
from sphinx.ext.autodoc import ClassDocumenter, ObjectMember


class AttrsClassDocumenter(ClassDocumenter):
    """ClassDocumenter that hides attrs fields defined with init=False."""

    objtype = "class"
    priority = ClassDocumenter.priority + 1  # override the default documenter

    def filter_members(
        self, members: list[ObjectMember], want_all: bool
    ) -> list[tuple[str, Any, bool]]:
        filtered = super().filter_members(members, want_all)

        if attrs.has(self.object):
            skip_names = {f.name for f in attrs.fields(self.object) if not f.init}
            filtered = [m for m in filtered if m[0] not in skip_names]

        return filtered


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the extension."""
    app.add_autodocumenter(AttrsClassDocumenter, override=True)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
