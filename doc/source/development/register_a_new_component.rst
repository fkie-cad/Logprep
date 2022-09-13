==========================
Registring a new Component
==========================

Registry
========

The :py:class:`logprep.registry.Registry` contains all currently supported logprep compontents 
(Connectors and Processors). When implementing a new component you have to register it in the
:py:class:`logprep.registry.Registry` by importing it and adding it to the code:`mapping`
attribute. This exposes it to the :py:class:`logprep.factory.Factory` which can automatically
create the correct instances, depending on the :code:`type` inside the components configuration.

Factory
=======

The :py:class:`~logprep.factory.Factory` reads the `type` field from components configurations,
retrieves the corresponding component class from the :py:class:`~logprep.registry.Registry` and
creates a proper object.
