# pylint: disable=missing-docstring
# pylint: disable=protected-access
import pytest
from Crypto.PublicKey import RSA

from logprep.processor.pseudonymizer.encrypter import DualPKCS1HybridEncrypter
from logprep.util.pseudo.keygenerator.generate_rsa_key import generate_keys


class TestPseudonymizer:

    @pytest.mark.parametrize(
        "analyst_key_length, depseudo_key_length",
        [(1024, 2048), (2048, 1024), (1024, 1024), (2048, 2048)],
    )
    def test_pseudonymize(self, analyst_key_length, depseudo_key_length):
        public_key_analyst, private_key_analyst = generate_keys(
            key_length=analyst_key_length,
        )
        public_key_depseudo, private_key_depseudo = generate_keys(key_length=depseudo_key_length)
        encrypter = DualPKCS1HybridEncrypter()
        encrypter._pubkey_analyst = RSA.import_key(public_key_analyst.decode("utf-8"))
        encrypter._pubkey_depseudo = RSA.import_key(public_key_depseudo.decode("utf-8"))
        value = "1"
        encrypted_origin = encrypter.encrypt(value)
        assert value != encrypted_origin
