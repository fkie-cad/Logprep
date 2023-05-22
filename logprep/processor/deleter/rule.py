"""
Rule Configuration
^^^^^^^^^^^^^^^^^^

The example below deletes the log message if the message field equals "foo".

..  code-block:: yaml
    :linenos:
    :caption: Example delete rule

    filter: 'message: "foo"'
    deleter:
        delete: true
    description: '...'

.. autoclass:: logprep.processor.deleter.rule.DeleterRule.Config
   :members:
   :undoc-members:
   :inherited-members:
   :noindex:
"""

from attrs import define, field, validators

from logprep.processor.base.rule import Rule


class DeleterRule(Rule):
    """Check if documents match a filter."""

    @define(kw_only=True)
    class Config(Rule.Config):
        """Config for DeleterRule"""

        delete: bool = field(validator=validators.instance_of(bool))
        """Delete or not"""
        target_field = field(init=False, repr=False, eq=False)

    @property
    def delete_event(self) -> bool:
        """Returns delete_or_not"""
        return self._config.delete
