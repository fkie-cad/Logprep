"""abstract module for components"""

import logging

from logprep.abc.component import Component

logger = logging.getLogger("Component")


class NgComponent(Component):
    """Abstract Component Class to define the Interface"""

    # pylint: disable=invalid-overridden-method, useless-parent-delegation
    # TODO fork ng-based Component properly
    # We override the setup to be async in the ng component tree.
    # This is unclean from an interface perspective, but works if the worlds doen't mix.

    async def setup(self) -> None:
        return super().setup()

    async def shut_down(self) -> None:
        return await super().shut_down()

    # pylint: enable=invalid-overridden-method,useless-parent-delegation
