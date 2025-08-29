"""
HTTPGeneratorOutput
===================

The logprep Http generator inheriting from the http connector output.
Sends the documents written by the generator to a http endpoint.
"""

import threading
from typing import overload

from logprep.connector.http.output import HttpOutput


class HttpGeneratorOutput(HttpOutput):
    """Output class inheriting from the connector output class"""

    def __init__(self, name, configuration):
        self.lock = threading.Lock()
        super().__init__(name, configuration)

    @overload
    def store(self, document: str) -> None: ...

    @overload
    def store(self, document: tuple[str, dict | list[dict]] | dict) -> None: ...

    def store(self, document) -> None:
        target, _, payload = document.partition(",")
        with self.lock:
            self.store_custom(payload, self._config.target_url + target)
