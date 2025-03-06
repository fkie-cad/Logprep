"""
HTTPGeneratorOutput
==========

The logprep Http generator inheriting from the http connector output.
Sends the documents writen by the generator to a http endpoint.
"""

from logprep.connector.http.output import HttpOutput


class HttpGeneratorOutput(HttpOutput):
    """Output class inheriting from the connector output class"""

    def store(self, document: tuple[str, dict | list[dict]] | dict | str) -> None:
        if isinstance(document, str):
            target, _, payload = document.partition(",")
            self.store_custom(payload, self._config.target_url + target)
        else:
            super().store(document)
