.. _dot_notation:

Dot Notation
============

Dot notation is used to refer to nested fields inside data structures in our configuration language.
For example, :code:`nested.field` refers to the field :code:`data["event"]["field"]` (Python syntax) inside a nested dictionary called :code:`data`.

This notation can be used throughout the application:

- Lucene-based rule filters: :code:`filter: "nested.field: *"`
- Read or written fields in processor configurations: e.g., :code:`source_fields: ["nested.field"]`, :code:`target_field: "nested.field"`
- Read or written fields in input configurations: e.g., :code:`metafield_name: "nested.field"``
- Read or written fields in output configurations


Escaping Special Characters
---------------------------

Since the dot is interpreted as a special character, it must be escaped with a backslash to be used literally:
:code:`complex\\.field` for addressing :code:`data["complex.field"]`.
Note that string literals with quotes typically require an additional layer of backslashes:
:code:`target_field: "complex\\\\.field"`.
If backslashes are part of the actual field name, they must also be escaped:
:code:`complex\\\\field` or :code:`"complex\\\\\\\\field"`.

Putting a backslash in front of a non-special character results in the *backslash being dropped* and the character being used literally.
Therefore, a literal backslash can only be produced by using a double backslash in the field reference.


Future Compatibility
--------------------

Dropping backslashes in front of non-special characters provides a downwards-compatible path for introducing new special characters in the syntax.
After announcing an upcoming change, users can start escaping the soon-to-be special character in their configuration files.
This ensures the character is interpreted literally in both the old and new versions, allowing for a seamless transition.
