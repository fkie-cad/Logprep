"""abstract module for components"""

import logging

from logprep.abc.component import Component

logger = logging.getLogger("Component")


class NgComponent(Component):
    """Abstract Component Class to define the Interface"""

    # pylint: disable=invalid-overridden-method, useless-parent-delegation
    # TODO fork ng-based Component properly
    # We override the setup to be async in the ng component tree.
    # This is unclean from an interface perspective, but works if the worlds don't mix.

    async def setup(self) -> None:
        """Set up the ng component."""

        super().setup()

    async def shut_down(self) -> None:
        """Shut down ng component and cleanup resources."""

        super().shut_down()

    async def health(self) -> bool:
        """Check the health of the component.

        Returns
        -------
        bool
            True if the component is healthy, False otherwise.

        """
        return super().health()

    # pylint: enable=invalid-overridden-method,useless-parent-delegation
