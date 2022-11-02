"""Template Replacer
====================

The template replacer requires the additional field :code:`template_replacer`.
No additional configuration parameters are required for the rules.
The module is completely configured over the pipeline configuration.

In the following example the target field specified in the processor configuration
is replaced for all log messages that have :code:`winlog.provider_name` and
:code:`winlog.event_id` if it is defined in the template file.

..  code-block:: yaml
    :linenos:
    :caption: Example

    filter: winlog.provider_name AND winlog.event_id
    template_replacer: {}
    description: ''

"""

from logprep.processor.base.rule import Rule


class TemplateReplacerRule(Rule):
    """Check if documents match a filter."""
