import re
from unittest import mock

import pytest

pytest.importorskip("logprep.processor.pseudonymizer")

from logprep.processor.pseudonymizer.encrypter import DualPKCS1HybridEncrypter

MOCK_PUBKEY_1024 = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCeS8jEtEdxU6gyWKIoORWmJnzn\n"
    "bw2RQ80JmgWsI/Qyh8ADYa02K/7fhP4oJasFPLPt1UHWjYZR4zY1qCyOdLkYOP+d\n"
    "eiiiKuds6+5od47HKlZdkoOdZiDQJ0sdtCVKPPmtRByDig4LEgaAwqAR0nMKpoH9\n"
    "PyLe/89Z6vPR3xZGywIDAQAB\n"
    "-----END PUBLIC KEY-----"
)

MOCK_PUBKEY_2048 = (
    "-----BEGIN PUBLIC KEY-----\n"
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwLKN7dDDDryF9MxoEQPa\n"
    "YIo9OQXQvRM39/VjcWfKRPZf4p/Fv5MMGYfrGrkOq4SCqKeim4FeDZGcRpnK7t6n\n"
    "X5cgec2xah8kq5DjhVYlHVik6B/CyttTWk7j6ueuompwvg5BFLOR+sPyxOxUkUSb\n"
    "4TtxRiU2GmNNq5rfWXoCHceQdOKsY+HgFz9zJPiBF2vfRV0wdEVlOOu78orJiglf\n"
    "9RzInui0HKvgMpT+5HfpC0ejdODT8nQ77bw56tNvX4LbSfOyYiEqxLu4hJHafuhL\n"
    "kIvdKlFT87zhbyjDwPgNNwcbyAFtDw4xqdM+isGpx/U3VqUGapOKHlj2Lq0gKtjL\n"
    "kQIDAQAB\n"
    "-----END PUBLIC KEY-----"
)

BASE64_REGEX = r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$"


class TestDualPKCS1HybridEncrypter:
    def test_encrypt_without_loaded_keys(self):
        encrypter = DualPKCS1HybridEncrypter()
        with pytest.raises(ValueError):
            encrypter.encrypt("foo")

    @mock.patch("logprep.processor.pseudonymizer.encrypter.open")
    def test_load_public_keys_successfully(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=MOCK_PUBKEY_1024).return_value,
            mock.mock_open(read_data=MOCK_PUBKEY_2048).return_value,
        ]
        encrypter = DualPKCS1HybridEncrypter()
        encrypter.load_public_keys("foo", "bar")
        assert len(str(encrypter._pubkey_analyst.n)) == 309
        assert len(str(encrypter._pubkey_depseudo.n)) == 617

    @mock.patch("logprep.processor.pseudonymizer.encrypter.open")
    def test_load_public_keys_invalid_key(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data="foo").return_value,
            mock.mock_open(read_data="bar").return_value,
        ]
        encrypter = DualPKCS1HybridEncrypter()
        with pytest.raises(ValueError):
            encrypter.load_public_keys("foo", "bar")

    def test_load_public_keys_invalid_path(self):
        encrypter = DualPKCS1HybridEncrypter()
        with pytest.raises(FileNotFoundError):
            encrypter.load_public_keys("non_existent_file_1", "non_existent_file_1")

    @mock.patch("logprep.processor.pseudonymizer.encrypter.open")
    def test_encrypt(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=MOCK_PUBKEY_1024).return_value,
            mock.mock_open(read_data=MOCK_PUBKEY_2048).return_value,
        ]
        encrypter = DualPKCS1HybridEncrypter()
        encrypter.load_public_keys("foo", "bar")
        output = encrypter.encrypt("foo")
        assert len(output) == (256 + 8 + len("foo")) * 4 / 3
        assert re.match(BASE64_REGEX, str(output))
