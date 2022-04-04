"""Configuration of the Clusterer"""

from types import SimpleNamespace


class SignatureProgramTags(SimpleNamespace):
    """Contains tags used to wrap signature terms."""

    start_tag = "<+>"
    end_tag = "</+>"
