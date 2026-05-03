"""abstract module for components"""

import asyncio
import logging
import sys

from logprep.abc.component import Component
from logprep.ng.util.defaults import EXITCODES

logger = logging.getLogger("Component")


class NgComponent(Component):
    """Abstract Component Class to define the Interface"""

    # pylint: disable=invalid-overridden-method, useless-parent-delegation
    # TODO fork ng-based Component properly
    # We override the setup to be async in the ng component tree.
    # This is unclean from an interface perspective, but works if the worlds don't mix.

    async def setup(self) -> None:  # type: ignore[override]
        """Set up the ng component."""

        self._populate_cached_properties()
        await self._wait_for_health()

    async def shut_down(self) -> None:  # type: ignore[override]
        """Shut down ng component and cleanup resources."""
        self._clear_scheduled_jobs()
        self._clear_properties()

    async def health(self) -> bool:  # type: ignore[override]
        """Check the health of the component.

        Returns
        -------
        bool
            True if the component is healthy, False otherwise.

        """
        return True

    async def _wait_for_health(self) -> None:  # type: ignore[override]
        """Wait for the component to be healthy.
        if the component is not healthy after a period of time, the process will exit.
        """
        for i in range(3):
            if await self.health():
                break
            logger.info("Wait for %s initially becoming healthy: %s/3", self.name, i + 1)
            await asyncio.sleep(1 + i)
        else:
            logger.error("Component '%s' did not become healthy", self.name)
            sys.exit(EXITCODES.PIPELINE_ERROR.value)

    # pylint: enable=invalid-overridden-method,useless-parent-delegation
