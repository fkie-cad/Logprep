# pylint: disable=missing-docstring
# pylint: disable=protected-access
import base64
import re
from unittest import mock

import pytest
from Crypto.PublicKey import RSA

from logprep.util.pseudo.encrypter import (
    DualPKCS1HybridCTREncrypter,
    DualPKCS1HybridGCMEncrypter,
)
from logprep.util.pseudo.keygenerator.generate_rsa_key import generate_keys

MOCK_PUBKEY_1024 = b"""-----BEGIN PUBLIC KEY-----
    MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCeS8jEtEdxU6gyWKIoORWmJnzn
    bw2RQ80JmgWsI/Qyh8ADYa02K/7fhP4oJasFPLPt1UHWjYZR4zY1qCyOdLkYOP+d
    eiiiKuds6+5od47HKlZdkoOdZiDQJ0sdtCVKPPmtRByDig4LEgaAwqAR0nMKpoH9
    PyLe/89Z6vPR3xZGywIDAQAB
    -----END PUBLIC KEY-----
    """


MOCK_PUBKEY_2048 = b"""-----BEGIN PUBLIC KEY-----
    MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwLKN7dDDDryF9MxoEQPa
    YIo9OQXQvRM39/VjcWfKRPZf4p/Fv5MMGYfrGrkOq4SCqKeim4FeDZGcRpnK7t6n
    X5cgec2xah8kq5DjhVYlHVik6B/CyttTWk7j6ueuompwvg5BFLOR+sPyxOxUkUSb
    4TtxRiU2GmNNq5rfWXoCHceQdOKsY+HgFz9zJPiBF2vfRV0wdEVlOOu78orJiglf
    9RzInui0HKvgMpT+5HfpC0ejdODT8nQ77bw56tNvX4LbSfOyYiEqxLu4hJHafuhL
    kIvdKlFT87zhbyjDwPgNNwcbyAFtDw4xqdM+isGpx/U3VqUGapOKHlj2Lq0gKtjL
    kQIDAQAB
    -----END PUBLIC KEY-----
    """


class TestDualPKCS1HybridCTREncrypter:
    def test_encrypt_without_loaded_keys(self):
        encrypter = DualPKCS1HybridCTREncrypter()
        with pytest.raises(ValueError):
            encrypter.encrypt("foo")

    @mock.patch("pathlib.Path.open")
    def test_load_public_keys_successfully(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=MOCK_PUBKEY_1024).return_value,
            mock.mock_open(read_data=MOCK_PUBKEY_2048).return_value,
        ]
        encrypter = DualPKCS1HybridCTREncrypter()
        encrypter.load_public_keys("foo", "bar")
        assert len(str(encrypter._pubkey_analyst.n)) == 309
        assert len(str(encrypter._pubkey_depseudo.n)) == 617

    @mock.patch("pathlib.Path.open")
    def test_load_public_keys_invalid_key(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=b"foo").return_value,
            mock.mock_open(read_data=b"bar").return_value,
        ]
        encrypter = DualPKCS1HybridCTREncrypter()
        with pytest.raises(ValueError):
            encrypter.load_public_keys("foo", "bar")

    def test_load_public_keys_invalid_path(self):
        encrypter = DualPKCS1HybridCTREncrypter()
        with pytest.raises(FileNotFoundError):
            encrypter.load_public_keys("non_existent_file_1", "non_existent_file_1")

    @pytest.mark.parametrize(
        "analyst_key_length, depseudo_key_length",
        [(1024, 2048)],
    )
    def test_pseudonymize_sucess(self, analyst_key_length, depseudo_key_length):
        public_key_analyst, private_key_analyst = generate_keys(
            key_length=analyst_key_length,
        )
        public_key_depseudo, private_key_depseudo = generate_keys(key_length=depseudo_key_length)
        encrypter = DualPKCS1HybridCTREncrypter()
        encrypter._pubkey_analyst = RSA.import_key(public_key_analyst.decode("utf-8"))
        encrypter._pubkey_depseudo = RSA.import_key(public_key_depseudo.decode("utf-8"))
        value = "1"
        encrypted_origin = encrypter.encrypt(value)
        assert value != encrypted_origin

    @mock.patch("pathlib.Path.open")
    def test_encrypt(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=MOCK_PUBKEY_1024).return_value,
            mock.mock_open(read_data=MOCK_PUBKEY_2048).return_value,
        ]
        encrypter = DualPKCS1HybridCTREncrypter()
        encrypter.load_public_keys("foo", "bar")
        output = encrypter.encrypt("foo")
        assert len(output.split(":")) == 3
        assert not output.endswith("foo")


class TestDualPKCS1HybridGCMEncrypter:

    @pytest.mark.parametrize(
        "analyst_key_length, depseudo_key_length",
        [(1024, 2048), (2048, 1024), (1024, 1024), (2048, 2048)],
    )
    def test_pseudonymize(self, analyst_key_length, depseudo_key_length):
        public_key_analyst, private_key_analyst = generate_keys(
            key_length=analyst_key_length,
        )
        public_key_depseudo, private_key_depseudo = generate_keys(key_length=depseudo_key_length)
        encrypter = DualPKCS1HybridGCMEncrypter()
        encrypter._pubkey_analyst = RSA.import_key(public_key_analyst.decode("utf-8"))
        encrypter._pubkey_depseudo = RSA.import_key(public_key_depseudo.decode("utf-8"))
        value = "1"
        encrypted_origin = encrypter.encrypt(value)
        assert value != encrypted_origin

    @mock.patch("pathlib.Path.open")
    def test_encrypt(self, mock_open):
        mock_open.side_effect = [
            mock.mock_open(read_data=MOCK_PUBKEY_1024).return_value,
            mock.mock_open(read_data=MOCK_PUBKEY_2048).return_value,
        ]
        encrypter = DualPKCS1HybridGCMEncrypter()
        encrypter.load_public_keys("foo", "bar")
        output = encrypter.encrypt("foo")
        assert len(output.split(":")) == 5
        assert not output.endswith("foo")
