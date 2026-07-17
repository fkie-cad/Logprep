"""Utility module for handling environment variables"""

import os
import re
from string import Template
from types import MappingProxyType

_ENV_SNAPSHOT = dict(os.environ)

ENV_VARS = MappingProxyType(_ENV_SNAPSHOT)


def del_env_var(name: str):
    """Remove an env var from :code:`os.environ` and the cached snapshot"""
    os.environ.pop(name, None)
    _ENV_SNAPSHOT.pop(name)


def set_env_var(name: str, value: str):
    """Set an env var in :code:`os.environ` and in the cache"""
    os.environ[name] = value
    _ENV_SNAPSHOT[name] = value


class EnvTemplate(Template):
    """Template class for uppercase only template variables"""

    pattern = r"""
        \$(?:
            (?P<escaped>\$\$\$)|
            (?P<named>(?!LOGPREP_LIST)(?=LOGPREP_|CI_|GITHUB_|PYTEST_)[_A-Z0-9]*)|
            {(?P<braced>(?!LOGPREP_LIST)(?=LOGPREP_|CI_|GITHUB_|PYTEST_)[_A-Z0-9]*)}|
            (?P<invalid>)
        )
    """  # type: ignore[assignment]

    flags = re.VERBOSE

    @property
    def compiled_pattern(self) -> re.Pattern[str]:
        """Return the compiled internal pattern used to identify vars"""
        # Template sets `pattern = re.compile(pattern)` internally
        return self.pattern  # type: ignore
