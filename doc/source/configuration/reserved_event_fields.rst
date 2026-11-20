.. _reserved-event-fields:

Reserved event fields
=====================

``@LOGPREP_EVENT_ID`` is reserved for internal event tracking. Incoming events must
not supply this field, and processing rules must not create, overwrite, rename, or
delete it. To choose the output field for the event ID, use the output's
``target_id_field`` setting.
