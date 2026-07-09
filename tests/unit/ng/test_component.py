# pylint: disable=missing-docstring

from logprep.ng.abc.component import NgComponent


class TestNgComponent:
    async def test_health_returns_false_after_shutdown(self):
        component = NgComponent("test", NgComponent.Config(type="test"))

        assert await component.health() is True

        await component.shut_down()

        assert await component.health() is False
