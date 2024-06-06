# pylint: disable=missing-docstring
# pylint: disable=protected-access
import base64

import pytest
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA

from logprep.processor.pseudonymizer.encrypter import DualPKCS1HybridEncrypter
from logprep.util.pseudo.depseudonymizer.depseudonymizer import (
    DepseudonymizeError,
    Depseudonymizer,
)
from logprep.util.pseudo.keygenerator.generate_rsa_key import generate_keys


@pytest.fixture(name="analyst_keys", scope="module")
def get_analyst_keys():
    return generate_keys(key_length=1024)


@pytest.fixture(name="depseudo_keys", scope="module")
def get_depseudo_keys():
    return generate_keys(key_length=2048)


def encrypt(plaintext, pubkey_analyst, pubkey_depseudo):

    encrypter = DualPKCS1HybridEncrypter()
    encrypter._pubkey_analyst = RSA.import_key(pubkey_analyst.decode("utf-8"))
    encrypter._pubkey_depseudo = RSA.import_key(pubkey_depseudo.decode("utf-8"))
    return encrypter.encrypt(plaintext)


class TestDepseudonymizer:
    def test_depseudonymize_manual(self, analyst_keys, depseudo_keys):
        privkey_analyst, pubkey_analyst = analyst_keys
        privkey_depseudo, pubkey_depseudo = depseudo_keys
        cipher_rsa_analyst = PKCS1_OAEP.new(RSA.import_key(privkey_analyst.decode("utf-8")))
        cipher_rsa_depseudo = PKCS1_OAEP.new(RSA.import_key(privkey_depseudo.decode("utf-8")))
        encrypted_value = encrypt(
            plaintext="1",
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )
        assert encrypted_value != "1"
        # split and decode encrypted value
        (
            session_key_enc_enc,
            aes_key_depseudo_nonce,
            depseudo_key_enc,
            aes_key_input_str_nonce,
            input_str_enc,
        ) = [base64.b64decode(encoded) for encoded in encrypted_value.split("||")]

        # decrypt encrypted encrypted session key with analyst private key
        session_key_enc: bytes = cipher_rsa_analyst.decrypt(session_key_enc_enc)

        # decrypt AES depseudo key with depseudo private key
        depseudo_key: bytes = cipher_rsa_depseudo.decrypt(depseudo_key_enc)

        # decrpyt session key with AES depseudo key
        aes_key = AES.new(depseudo_key, AES.MODE_GCM, aes_key_depseudo_nonce)
        session_key: bytes = aes_key.decrypt(session_key_enc)

        # decrypt ciphertext with AES session key
        aes_key_input_str = AES.new(session_key, AES.MODE_GCM, aes_key_input_str_nonce)
        decrypted_value: str = aes_key_input_str.decrypt(input_str_enc).decode("utf-8")

        assert decrypted_value == "1"

    def test_depseudonymizer_populates_properties(self, analyst_keys, depseudo_keys):
        _, pubkey_analyst = analyst_keys
        _, pubkey_depseudo = depseudo_keys
        encrypted_value = encrypt(
            plaintext="1",
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )

        depseudo = Depseudonymizer(encrypted_value)
        encrypted_value_b64decoded = base64.b64decode(encrypted_value)
        assert depseudo.pseudonymized_string == encrypted_value_b64decoded
        assert depseudo.encrypted_session_key == encrypted_value_b64decoded[:256]
        assert depseudo.cipher_nonce == encrypted_value_b64decoded[256:264]
        assert depseudo.ciphertext == encrypted_value_b64decoded[264:]

    def test_depseudonymizer_depseudonymize_raises_if_no_depseudo_key(
        self, analyst_keys, depseudo_keys
    ):
        _, pubkey_analyst = analyst_keys
        _, pubkey_depseudo = depseudo_keys
        encrypted_value = encrypt(
            plaintext="1",
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )

        depseudo = Depseudonymizer(encrypted_value)
        with pytest.raises(DepseudonymizeError, match=r"No depseudo key"):
            depseudo.depseudonymize()

    def test_depseudonymizer_depseudonymize_raises_if_no_analyst_key(
        self, analyst_keys, depseudo_keys
    ):
        _, pubkey_analyst = analyst_keys
        privkey_depseudo, pubkey_depseudo = depseudo_keys
        encrypted_value = encrypt(
            plaintext="1",
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )

        depseudo = Depseudonymizer(encrypted_value)
        depseudo.depseudo_key = privkey_depseudo.decode("utf-8")
        with pytest.raises(DepseudonymizeError, match=r"No analyst key"):
            depseudo.depseudonymize()

    @pytest.mark.parametrize(
        "plaintext",
        [
            "1",
            "message",
            "second_message",
            "asökdfjqqiweuraö",
            "23884ß10239847ß",
            "§$RFWSF",
            "askjf2q903rui0üajfdskalsdhfkj9pw8ue7rfdaödsjiöaldfjfjq093r7uüadsjfaskdjfu20984r290fda6ds5f4a6sd54fa65sdff4asd2f1a6s5d4fa6s5df4asdf4a6sd54fa6s5d4füojedsaüfjk",  # pylint: disable=line-too-long
            """
            asdkfjasödlfkj
            asdkfjasdufasopid
            237429034
            """,
        ],
    )
    def test_depseudonymizer_depseudonymize_messages(self, analyst_keys, depseudo_keys, plaintext):
        privkey_analyst, pubkey_analyst = analyst_keys
        privkey_depseudo, pubkey_depseudo = depseudo_keys
        encrypted_value = encrypt(
            plaintext=plaintext,
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )

        depseudo = Depseudonymizer(encrypted_value)
        depseudo.depseudo_key = privkey_depseudo.decode("utf-8")
        depseudo.analyst_key = privkey_analyst.decode("utf-8")
        assert depseudo.depseudonymize() == plaintext
