# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access

import pytest

from logprep.ng.connector.dummy.input import DummyInput
from tests.unit.ng.connector.base import BaseInputTestCase


class DummyError(Exception):
    pass


class TestDummyInput(BaseInputTestCase[DummyInput]):
    timeout = 0.01

    CONFIG = {"type": "ng_dummy_input", "documents": []}

    async def test_fails_with_disconnected_error_if_input_was_empty(self):
        await self.object.setup()

        with pytest.raises(StopAsyncIteration):
            await self.object.get_next(self.timeout)

    async def test_returns_documents_in_order_provided(self):
        self.object = self._create_test_instance(
            config_patch={
                "documents": [
                    {"order": 0},
                    {"order": 1},
                    {"order": 2},
                ]
            }
        )

        await self.object.setup()

        for order in range(0, 3):
            event = await self.object.get_next(self.timeout)
            assert event.data.get("order") == order

    async def test_returns_documents_and_raises_exceptions_with_mixed_types(self):
        self.object = self._create_test_instance(
            config_patch={
                "documents": [
                    {"order": 0},
                    DummyError(),
                    {"order": 1},
                    DummyError,
                ]
            }
        )

        await self.object.setup()

        assert (await self.object.get_next(self.timeout)).data.get("order") == 0

        with pytest.raises(DummyError):
            await self.object.get_next(self.timeout)

        assert (await self.object.get_next(self.timeout)).data.get("order") == 1

        with pytest.raises(DummyError):
            await self.object.get_next(self.timeout)

    async def test_repeat_documents_repeats_documents(self):
        self.object = self._create_test_instance(
            config_patch={
                "documents": [{"order": 0}, {"order": 1}, {"order": 2}],
                "repeat_documents": True,
            }
        )

        await self.object.setup()

        for order in range(0, 9):
            event = await self.object.get_next(self.timeout)
            assert event.data.get("order") == order % 3

    async def test_dummy_input_iterator(self):
        self.object = self._create_test_instance(
            config_patch={
                "documents": [{"order": 0}, {"order": 1}, {"order": 2}],
            }
        )

        await self.object.setup()

        with pytest.raises(StopAsyncIteration):
            dummy_input_iterator = self.object

            assert (await anext(dummy_input_iterator)).data == {"order": 0}
            assert (await anext(dummy_input_iterator)).data == {"order": 1}
            assert (await anext(dummy_input_iterator)).data == {"order": 2}
            assert (await anext(dummy_input_iterator)) is None
