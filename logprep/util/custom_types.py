"""Custon types to be used in logprep"""

import click


class BoolOrStr(click.ParamType):
    """Defines a Click parameter type that accepts either a boolean or a string.

    This allows for implementing a boolean switch that also accepts a filepath or URL.

    Examples:
        --verify true   → True (boolean)
        --verify false  → False (boolean)
        --verify /path/to/file  → "/path/to/file" (string)
        --verify http://example.com → "http://example.com" (string)
    """

    name = "bool-or-str"

    def convert(self, value, param, ctx):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lower_val = value.lower()
            if lower_val in ["true", "false"]:
                return lower_val == "true"
            return value
        raise click.BadParameter(
            f"{value!r} is not a valid parameter type. Expected a boolean or string."
        )
