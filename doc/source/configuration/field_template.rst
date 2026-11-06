.. _field_template:

Field templates
===============

Field templates build a mapping from literal values and expressions.
Use them in processor options that explicitly support templates, such as the
selective extractor's :ref:`event_template <selective_extractor_event_template>`.
They are not (yet) expanded in other configuration options.

This page describes the shared syntax, default functions, and error behavior.
Each processor documents its template option, available data, supported
functions, and error handling.

Building a template
-------------------

A template is a YAML mapping. It can contain nested mappings, lists, strings,
numbers, booleans, and null values. An expression occupies an entire string and
is enclosed in ``${...}``:

.. code-block:: yaml

    message: '${source_event.message}'
    service: payments
    retries: 3
    enabled: true
    optional: null
    metadata:
      host: '${source_event.host.name}'
    labels:
      - audit
      - '${source_event.category}'

The examples in this section assume usage inside a processor rule. All
``event_template`` options in processor rules provide ``source_event`` as the
incoming event to be processed. Place these mappings inside the rule's
``event_template`` option.

An expression preserves the referenced value's type.
For example, if ``source_event.retries`` is the number ``3``,
``'${source_event.retries}'`` produces a number, not the string ``"3"``.
A referenced list or mapping remains a list or mapping.
To produce a string, use ``'${source_event.retries | str}'``.
See :ref:`field_template_errors` for missing-field and failure behavior.

Expression results are used as values, without interpreting them as further
templates. Keys inside a mapping obtained by a lookup are also preserved as they
are; the output-path rules below apply to keys written in the template itself.

Looking up fields
-----------------

A lookup starts with a context name supplied by the processor, followed by one
or more field names using the usual :doc:`dot notation <dot_notation>`:

.. code-block:: yaml

    timestamp: '${source_event.@timestamp}'
    host: '${source_event.host.name}'
    first_tag: '${source_event.tags.0}'

Numeric lookup segments select list elements using zero-based indexes. There
must be no whitespace around the dots. A bare context name such as
``${source_event}`` is unsupported; select a field within it.

Escape special characters in field names with a backslash. For example,
``'${source_event.host\.name}'`` reads the single field named ``host.name``,
whereas ``'${source_event.host.name}'`` reads ``name`` inside ``host``.
See :ref:`field_template_escaping` for more examples.

Output keys and nested paths
----------------------------

Literal keys containing unescaped dots create nested mappings. Paths can share
a parent:

.. code-block:: yaml

    host.name: '${source_event.hostname}'
    host.type: server

For a source event with ``hostname: web-01``, this produces:

.. code-block:: yaml

    host:
      name: web-01
      type: server

Keys can also be whole expressions:

.. code-block:: yaml

    '${source_event.output_field}': '${source_event.value}'

With ``output_field: http.status`` and ``value: 200``, the result is
``{"http": {"status": 200}}``. The resolved key must be a string. Use
``'${source_event.id | str}'`` if a numeric ID should become a key.
An escaped dot in a resolved key denotes a literal dot, just as it does in a
literal template key.

Each output path must have a single assignment. Duplicate paths are errors;
they do not overwrite earlier values. Assigning both a parent and a child path
is also an error, even if the parent is assigned a mapping. For example, this
template is invalid:

.. code-block:: yaml

    host:
      name: web-01
    host.type: server

Instead, put both fields inside ``host``, or write both as dotted paths.
These rules also apply when expression keys resolve to the same or overlapping
paths.

Output paths cannot contain numeric segments in a multi-segment path:
``items.0`` and ``0.name`` are unsupported, even if the number is escaped.
To create a list, write a YAML list. To create a mapping with a numeric field
name, use an explicit nested mapping with quoted string keys:

.. code-block:: yaml

    codes:
      '0': success

.. _field_template_calls:

Function calls and pipes
------------------------

Functions transform values or combine them. A standalone call requires
parentheses:

.. code-block:: yaml

    id: '${str(source_event.id)}'
    normalized_name: '${lower(strip(source_event.name))}'
    message: '${concat("User ", source_event.name, " logged in")}'

A pipe passes its left-hand value as the first argument of the next function.
Pipes run from left to right. These two expressions have the same result:

.. code-block:: yaml

    name_by_call: '${lower(strip(source_event.name))}'
    name_by_pipe: '${source_event.name | strip | lower}'

Pipe functions without additional arguments may omit parentheses. Additional
arguments follow the piped value:

.. code-block:: yaml

    tags: '${source_event.tags | join(", ")}'
    prefixed: '${concat("Tags: ", join(source_event.tags, ", "))}'

Functions support positional and named arguments according to their documented
signatures. For example:

.. code-block:: yaml

    tags: '${join(source_event.tags, separator=", ")}'

Positional arguments must come before named arguments, and a named argument
cannot be repeated. A function name must immediately precede ``(``.
Trailing commas are unsupported.

Arguments can be lookups, nested calls, piped expressions, or these literals:

* Strings in single or double quotes: ``"hello"`` or ``'hello'``.
* Signed decimal integers: ``42``, ``-5``, ``+10``, ``1_000``.
* Decimal or scientific-notation numbers: ``3.14``, ``-0.5``, ``1e3``.
* Booleans: ``true`` and ``false`` (also ``True`` and ``False``).
* Null: ``none`` (also ``None``). Inside expressions, ``null`` is not a null literal.

Use ordinary YAML values for standalone literals. Expressions such as ``${42}``
and ``${"hello"}`` are unsupported; literals are supported as function arguments.

.. _field_template_default_functions:

Default functions
-----------------

The following functions form the default set. A processor's documentation states
which functions are available there and describes any additional functions.
Names are case-sensitive.

.. list-table:: Function reference
   :header-rows: 1
   :widths: 22 48 30

   * - Signature
     - Behavior and accepted input
     - Example and result
   * - ``str(x)``
     - Converts any value to text, including lists, mappings, and null. This is
       not JSON serialization: null becomes ``"None"``, booleans become
       ``"True"`` or ``"False"``, and containers use Python's text representation.
     - ``str(42)`` → ``"42"``
   * - ``int(x)``
     - Converts an integer, floating-point number, boolean, or integer string to
       an integer. Floating-point values are truncated toward zero. Strings
       must represent base-10 integers; ``"3.5"`` is invalid. No base argument
       is supported. Null, mappings, and lists are invalid.
     - ``int("42")`` → ``42``; ``int(-3.9)`` → ``-3``
   * - ``float(x)``
     - Converts a number, boolean, or numeric string to a floating-point number.
       Numeric strings may use scientific notation. Null, mappings, and lists
       are invalid.
     - ``float("1.5")`` → ``1.5``
   * - ``lower(x)``
     - Returns a lowercase string. Requires a string; it does not first convert
       other values to text.
     - ``lower("API")`` → ``"api"``
   * - ``upper(x)``
     - Returns an uppercase string. Requires a string.
     - ``upper("api")`` → ``"API"``
   * - ``strip(x)``
     - Removes leading and trailing whitespace from a string. Whitespace inside
       the string is preserved. Requires a string; a custom set of characters
       to remove is unsupported.
     - ``strip("  a b  ")`` → ``"a b"``
   * - ``join(values, separator)``
     - Joins a list of strings using the supplied string separator. Every item
       must already be a string. An empty list produces an empty string. A
       string input joins its individual characters.
     - For tags ``["a", "b"]``, ``join(source_event.tags, ", ")`` → ``"a, b"``
   * - ``concat(*values)``
     - Concatenates any number of strings without a separator. All arguments
       must be strings. No arguments produces an empty string.
     - ``concat("web", "-", "01")`` → ``"web-01"``

For ``str``, ``int``, ``float``, ``lower``, ``upper``, and ``strip``, the single
argument can also be named ``x``. ``join`` accepts ``values`` and ``separator``
as keyword names; ``concat`` accepts positional arguments only.

Convert explicitly when needed: ``'${source_event.id | str | lower}'``.

.. _field_template_errors:

Missing fields and invalid templates
-----------------------------------

Invalid syntax, unknown functions, and incorrect argument names or counts are
configuration errors.

During evaluation, a missing field causes an error, including when the lookup
appears in a function argument, a list element, or an output key.
A present null value is not a missing field.
Functions also require suitable input values.
For example, ``int("unknown")`` and ``lower(42)`` fail.
Such failures are not handled as missing fields.
See `Output keys and nested paths`_ for constraints on output keys and paths.
Functions do not provide automatic fallback values for missing fields or failed
conversions.
If evaluation fails, no partial mapping is returned.

Each processor documents how it handles these errors.

.. _field_template_escaping:

Quoting and escaping
--------------------

Use YAML single-quoted strings for expressions when possible: YAML then leaves
backslashes intact. Inside YAML single quotes, write two single quotes to
represent one, or use double quotes for string arguments as in the examples above.

A template backslash makes the next character literal. This applies to ordinary
template text, lookup field names, and quoted function arguments:

.. code-block:: yaml

    literal_expression: '\${source_event.message}'
    literal_backslash: 'C:\\logs'
    'host\.name': '${source_event.host\.name}'
    quoted_text: '${concat("Say \"hello\"", "!")}'

The first value is the literal text ``${source_event.message}``. The second is
``C:\logs``. The third copies the source field named ``host.name`` to an output
field with that same literal name. The fourth produces ``Say "hello"!``.

Backslash escapes do not translate ``\n`` or ``\t`` into newline or tab
characters: they produce ``n`` or ``t``. A literal backslash requires ``\\``;
a trailing unpaired backslash is invalid. YAML double-quoted strings have their
own escape rules, so backslashes intended for the template must also be escaped
for YAML.

Current limits
--------------

* Expressions must occupy an entire string. ``'Hello ${source_event.name}'`` is
  unsupported. Use ``'${concat("Hello ", source_event.name)}'`` instead.
* Expressions cannot mix literal key segments with an expression, such as
  ``'host.${source_event.name}'``. Use a whole expression returning the desired
  path, for example ``'${concat("host.", source_event.name)}'``.
* The expression language provides lookups and the functions supported by the
  processor. Arithmetic, comparisons, conditions, loops, comprehensions, method
  calls, and arbitrary Python expressions are unsupported.
* List and mapping literals cannot be written inside expressions. Write them as
  YAML containers, or reference existing source fields containing them.
* Bracket indexing and wildcard lookups are unsupported. Use dotted lookup
  paths, including numeric segments for list indexes.

Worked example
--------------

Given this source event:

.. code-block:: yaml

    user:
      id: 42
      name: '  ALICE  '
    tags: [login, audit]
    output_field: audit.action
    action: login

This template:

.. code-block:: yaml

    user.id: '${source_event.user.id | str}'
    user.name: '${source_event.user.name | strip | lower}'
    summary: '${concat("Tags: ", join(source_event.tags, ", "))}'
    '${source_event.output_field}': '${source_event.action}'
    categories:
      - security
      - '${source_event.tags.0}'

Produces:

.. code-block:: yaml

    user:
      id: '42'
      name: alice
    summary: 'Tags: login, audit'
    audit:
      action: login
    categories:
      - security
      - login
