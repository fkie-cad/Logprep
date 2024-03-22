"""This module is used to generate the current version of the package"""

from importlib.metadata import PackageNotFoundError, version


def get_versions() -> dict:
    """generate the current version of the package"""
    try:
        version_str = version("logprep")
    except PackageNotFoundError:  # pragma: no cover
        version_str = "unknown"
    return {"version": version_str}
