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
        ((EventStateType.ACKED, EventStateType.PROCESSING), 2),
        ((EventStateType.ACKED, EventStateType.PROCESSING, EventStateType.ACKED), 2),
        ((EventStateType.PROCESSING, EventStateType.PROCESSING), 3),
    ],
    ids=["1*ACKED+1*PROC→2", "2*ACKED+1*PROC→2", "2*PROC→3"],
)
def ack_cases(request):
    states, new_size = request.param
    backlog = {
        LogEvent(data={"message": f"msg {i+1}"}, original=b"", state=s)
        for i, s in enumerate(states, start=1)
    }
    return {"backlog": backlog, "initial_size": len(backlog), "new_size": new_size}
