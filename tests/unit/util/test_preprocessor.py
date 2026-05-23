# pylint: disable=duplicate-code
# pylint: disable=missing-docstring
# pylint: disable=protected-access
# pylint: disable=line-too-long
# pylint: disable=unnecessary-dunder-call
# pylint: disable=too-many-lines
# pylint: disable=unused-argument

import msgspec
import pytest

from logprep.ng.util.preprocessor import Preprocessor
from logprep.util.preprocessor import HmacConfig, PreprocessingConfig


class TestPreprocessor:

    @pytest.fixture
    def empty_preprocessor_config(self) -> PreprocessingConfig:
        return PreprocessingConfig()

    @pytest.fixture
    def preprocessor(self, empty_preprocessor_config) -> Preprocessor:
        return Preprocessor(
            empty_preprocessor_config,
            {},
            msgspec.json.Decoder(type=dict),
            msgspec.json.Encoder(),
        )

    def test_add_hmac_to_adds_hmac(self, preprocessor: Preprocessor):
        processed_event = preprocessor._add_hmac_to(
            {"message": "test message"},
            b"test message",
            HmacConfig(target="<RAW_MSG>", key="hmac-test-key", output_field="Hmac"),
        )
        hmac = processed_event["Hmac"]["hmac"]
        assert hmac == "cc67047535dc9ac17775785b05fe8cdd245387e2d036b2475e82f37653c5bf3d"
        compressed_base64 = processed_event["Hmac"]["compressed_base64"]
        assert compressed_base64 == "eJwrSS0uUchNLS5OTE8FAB8fBMY="

    def test_add_hmac_to_adds_hmac_even_if_no_raw_message_was_given(
        self, preprocessor: Preprocessor
    ):
        processed_event = preprocessor._add_hmac_to(
            {"message": "test message"},
            None,
            HmacConfig(target="<RAW_MSG>", key="hmac-test-key", output_field="Hmac"),
        )
        hmac = processed_event["Hmac"]["hmac"]
        assert hmac == "8b2d75efcba66476e5551d44065128bacff2f090db5b08d7a0201c33e3f651f5"
        compressed_base64 = processed_event["Hmac"]["compressed_base64"]
        assert compressed_base64 == "eJyrVspNLS5OTE9VslIqSS0uUYBxawF+Fwll"
