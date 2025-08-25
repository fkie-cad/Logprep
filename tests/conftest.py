"""
Global pytest configuration and shared fixtures.

This module is automatically discovered by pytest and does not need to be imported
explicitly. All fixtures defined here are available across the entire test suite.

Notes
-----
- Place common fixtures (e.g., database connections, test data generators, parametrized cases)
  here to avoid duplication.
- You can also implement pytest hooks in this file (e.g., pytest_configure,
  pytest_generate_tests).
- Do not import conftest.py directly; pytest injects it into the test discovery process.
"""

import pytest

from logprep.ng.event.event_state import EventStateType
from logprep.ng.event.log_event import LogEvent


@pytest.fixture(
    params=[
        (
            (EventStateType.ACKED, EventStateType.PROCESSING),
            2,
            "expecting: 1*ACKED will be removed from backlog",
        ),
        (
            (EventStateType.ACKED, EventStateType.PROCESSING, EventStateType.ACKED),
            2,
            "expecting: 2*ACKED will be removed from backlog",
        ),
        (
            (EventStateType.PROCESSING, EventStateType.PROCESSING),
            3,
            "expecting: no event state will be changed",
        ),
        (
            (EventStateType.DELIVERED, EventStateType.DELIVERED),
            3,
            "expecting: 2*DELIVERED should switch to ACKED (both events)",
        ),
    ],
    ids=["1*ACKED+1*PROCESSING→2", "2*ACKED+1*PROCESSING→2", "2*PROCESSING→3", "2*DELIVERED→3"],
)
def ack_cases(request):
    states, new_size, expected_message = request.param
    backlog = {
        LogEvent(data={"message": f"msg {i+1}"}, original=b"", state=s)
        for i, s in enumerate(states, start=1)
    }
    return {
        "backlog": backlog,
        "initial_size": len(backlog),
        "new_size": new_size,
        "expected_message": expected_message,
    }
