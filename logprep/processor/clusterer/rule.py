"""
Clusterer
=========

Rules of the clusterer are evaluated in alphanumerical order.
Some rules do only make sense if they are performed in a sequence with other rules.
The clusterer matches multiple rules at once and applies them all before creating a
clustering signature.
Therefore, it is recommended to prefix rules with numbers, i.e. `00_01_*`.
Here the first two digits represent a type of rules that make sense together and the second digits
represent the order of rules of the same type.

A subset of terms from this field can be extracted into the clustering-signature field defined in
the clusterer configuration.



Since clusterer rules must be used in a sequence, it makes no sense to perform regular
auto tests on them.
Thus, every rule can have a field :code:`tests` containing signature calculation tests.
It can contain one test or a list of tests.
Each tests consists of the fields :code:`tests.raw` and :code:`tests.result`.
:code:`tests.raw` is the input and would be usually the message.
:code:`tests.result` is the expected result.

..  code-block:: yaml
    :linenos:
    :caption: Example - One Test

    filter: ...
    clusterer: ...
    tests:
      raw:    'Some message'
      result: 'Some changed message'

..  code-block:: yaml
    :linenos:
    :caption: Example - Multiple Test

    filter: ...
    clusterer: ...
    tests:
      - raw:    'Some message'
        result: 'Some changed message'
      - raw:    'Another message'
        result: 'Another changed message'

In the following rule example the word `byte` is stemmed.

..  code-block:: yaml
    :linenos:
    :caption: Example - Stemming Rule

    filter: message
    clusterer:
      target: message
      pattern: '(bytes|Bytes|Byte)'
      repl: 'byte'
    description: '...'
    tests:
      raw:    'Byte is a Bytes is a bytes is a byte'
      result: 'byte is a byte is a byte is a byte'

In the following rule example the word `baz` is removed.

..  code-block:: yaml
    :linenos:
    :caption: Example - Removal Rule

    filter: message
    clusterer:
      target: message
      pattern: 'foo (bar) baz'
      repl: ''
    description: '...'
    tests:
      raw:    'foo bar baz'
      result: 'foo  baz'

In the following rule example the word `baz` is surrounded by extraction tags.

..  code-block:: yaml
    :linenos:
    :caption: Example - Extraction Rule

    filter: message
    clusterer:
      target: message
      pattern: 'foo (bar) baz'
      repl: '<+>\1</+>'
    description: '...'
    tests:
      raw:    'foo bar baz'
      result: 'foo <+>bar</+> baz'"""

import re
from typing import Pattern
from attrs import define, field, validators

from logprep.processor.base.rule import Rule


class ClustererRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """RuleConfig for Clusterer"""

        target: str = field(validator=validators.instance_of(str))
        """Defines which field should be used for clustering."""
        pattern: Pattern = field(validator=validators.instance_of(Pattern), converter=re.compile)
        """Defines the regex pattern that will be matched on the :code:`clusterer.target`."""
        repl: str = field(validator=validators.instance_of(str))
        """Anything within a capture group in :code:`clusterer.pattern` will be substituted with
        values defined in :code:`clusterer.repl`.
        The clusterer will only extract terms into a signature that are surrounded by the tags `<+></+>`.
        One could first use rules to remove common terms, other rules to perform stemming and finally
        rules to wrap terms in `<+></+>` to create a signature.

        For example:
        * Setting :code:`clusterer.repl: ''` would remove anything within a capture group.
        * Setting :code:`clusterer.repl: 'FOO'` would replace anything within a capture group with `FOO`.
        * Setting :code:`clusterer.repl: '<+>\1</+>'` would surround anything within a capture group with `<+></+>`.
        """

    # pylint: disable=C0111
    @property
    def pattern(self) -> Pattern:
        return self._config.pattern

    @property
    def repl(self) -> str:
        return self._config.repl

    # pylint: enable=C0111
