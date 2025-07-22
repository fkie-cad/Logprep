# pylint: disable=missing-docstring
# pylint: disable=attribute-defined-outside-init
# pylint: disable=protected-access
import copy
from itertools import cycle
from unittest import mock

import pytest

from logprep.factory import Factory
from logprep.ng.abc.input import CriticalInputError, SourceDisconnectedWarning
from tests.unit.ng.connector.base import BaseInputTestCase


class TestJsonInput(BaseInputTestCase):
    timeout = 0.1

    CONFIG = {"type": "ng_json_input", "documents_path": "/does/not/matter"}

    def test_documents_returns(self):
        return_value = [{"message": "test_message"}]

        with self.patch_documents_property(document=return_value):
            config = copy.deepcopy(self.CONFIG)
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            assert connector._documents == return_value

    def test_get_next_returns_document(self):
        return_value = [{"message": "test_message"}]

        with self.patch_documents_property(document=return_value):
            expected = return_value[0]

            config = copy.deepcopy(self.CONFIG)
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            document = connector.get_next(self.timeout)
            assert document.data == expected

    def test_get_next_returns_multiple_documents(self):
        return_value = [{"order": 0}, {"order": 1}]

        with self.patch_documents_property(document=return_value):
            config = copy.deepcopy(self.CONFIG)
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            event = connector.get_next(self.timeout)
            assert {"order": 0} == event.data
            event = connector.get_next(self.timeout)
            assert {"order": 1} == event.data

    def test_raises_exception_if_not_a_dict(self):
        return_value = ["no dict"]

        with self.patch_documents_property(document=return_value):
            config = copy.deepcopy(self.CONFIG)
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            with pytest.raises(CriticalInputError, match=r"not a dict"):
                _, _ = connector.get_next(self.timeout)

    def test_raises_exception_if_one_element_is_not_a_dict(self):
        return_value = [{"order": 0}, "not a dict", {"order": 1}]

        with self.patch_documents_property(document=return_value):
            config = copy.deepcopy(self.CONFIG)
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            with pytest.raises(CriticalInputError, match=r"not a dict"):
                _ = connector.get_next(self.timeout)
                _ = connector.get_next(self.timeout)
                _ = connector.get_next(self.timeout)

    def test_repeat_documents_repeats_documents(self):
        class CycledPopList:
            def __init__(self, iterable):
                self._iter = cycle(iterable)

            def pop(self, index=None):
                if index != 0:
                    raise IndexError("Only pop(0) supported in CycledPopList mock")
                return next(self._iter)

        cycled_list = CycledPopList([{"order": 0}, {"order": 1}, {"order": 2}])

        with mock.patch(
            "logprep.ng.connector.json.input.JsonInput._documents",
            new=mock.PropertyMock(return_value=cycled_list),
        ):
            config = copy.deepcopy(self.CONFIG)
            config["repeat_documents"] = True
            connector = Factory.create(configuration={"Test Instance Name": config})
            connector.setup()

            with mock.patch.dict(connector.__dict__, {"_documents": None}):
                for order in range(0, 9):
                    event = connector.get_next(self.timeout)
                    assert event.data.get("order") == order % 3

    @pytest.mark.skip(reason="not implemented")
    def test_setup_calls_wait_for_health(self):
        pass

    def test_json_input_iterator(self):
        return_value = [{"order": 0}, {"order": 1}, {"order": 2}]

        with self.patch_documents_property(document=return_value):
            config = copy.deepcopy(self.CONFIG)
            config["repeat_documents"] = False
            json_input_connector = Factory.create(configuration={"Test Instance Name": config})
            json_input_connector.setup()

            json_input_iterator = json_input_connector(timeout=self.timeout)
            assert next(json_input_iterator).data == {"order": 0}
            assert next(json_input_iterator).data == {"order": 1}
            assert next(json_input_iterator).data == {"order": 2}

            with pytest.raises(SourceDisconnectedWarning):
                next(json_input_iterator)
