# pylint: disable=missing-docstring
# pylint: disable=protected-access
import base64

import pytest
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA

from logprep.util.pseudo.decrypter import (
    CTRPseudonym,
    DecrypterError,
    DualPKCS1HybridCTRDecrypter,
    DualPKCS1HybridGCMDecrypter,
    GCMPseudonym,
)
from logprep.util.pseudo.encrypter import (
    DualPKCS1HybridCTREncrypter,
    DualPKCS1HybridGCMEncrypter,
)
from logprep.util.pseudo.keygenerator.generate_rsa_key import generate_keys


@pytest.fixture(name="analyst_keys", scope="module")
def get_analyst_keys():
    return generate_keys(key_length=1024)


@pytest.fixture(name="depseudo_keys", scope="module")
def get_depseudo_keys():
    return generate_keys(key_length=2048)


def encrypt_ctr_mode(plaintext, pubkey_analyst, pubkey_depseudo):

    encrypter = DualPKCS1HybridCTREncrypter()
    encrypter._pubkey_analyst = RSA.import_key(pubkey_analyst.decode("utf-8"))
    encrypter._pubkey_depseudo = RSA.import_key(pubkey_depseudo.decode("utf-8"))
    return encrypter.encrypt(plaintext)


def encrypt_gcm_mode(plaintext, pubkey_analyst, pubkey_depseudo):

    encrypter = DualPKCS1HybridGCMEncrypter()
    encrypter._pubkey_analyst = RSA.import_key(pubkey_analyst.decode("utf-8"))
    encrypter._pubkey_depseudo = RSA.import_key(pubkey_depseudo.decode("utf-8"))
    return encrypter.encrypt(plaintext)


class TestDualPKCS1HybridGCMDecrypter:
    def test_depseudonymize_manual(self, analyst_keys, depseudo_keys):
        privkey_analyst, pubkey_analyst = analyst_keys
        privkey_depseudo, pubkey_depseudo = depseudo_keys
        cipher_rsa_analyst = PKCS1_OAEP.new(RSA.import_key(privkey_analyst.decode("utf-8")))
        cipher_rsa_depseudo = PKCS1_OAEP.new(RSA.import_key(privkey_depseudo.decode("utf-8")))
        encrypted_value = encrypt_gcm_mode(
            plaintext="1",
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )
        assert encrypted_value != "1"
        # split and decode encrypted value
        encrypted_value: GCMPseudonym = GCMPseudonym(
            *[base64.b64decode(value) for value in encrypted_value.split(":")]
        )
        session_key_enc_enc = encrypted_value.session_key_enc_enc
        aes_key_depseudo_nonce = encrypted_value.aes_key_depseudo_nonce
        depseudo_key_enc = encrypted_value.depseudo_key_enc
        aes_key_input_str_nonce = encrypted_value.aes_key_input_str_nonce
        input_str_enc = encrypted_value.ciphertext

        # decrypt double encrypted session key with analyst private key
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

    def test_depseudonymizer_depseudonymize_raises_if_no_depseudo_key(
        self, analyst_keys, depseudo_keys
    ):
        _, pubkey_analyst = analyst_keys
        _, pubkey_depseudo = depseudo_keys
        encrypted_value = encrypt_gcm_mode(
            plaintext="1",
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )

        depseudo = DualPKCS1HybridGCMDecrypter(encrypted_value)
        with pytest.raises(DecrypterError, match=r"No depseudo key"):
            depseudo.decrypt()

    def test_depseudonymizer_depseudonymize_raises_if_no_analyst_key(
        self, analyst_keys, depseudo_keys
    ):
        _, pubkey_analyst = analyst_keys
        privkey_depseudo, pubkey_depseudo = depseudo_keys
        encrypted_value = encrypt_gcm_mode(
            plaintext="1",
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )

        depseudo = DualPKCS1HybridGCMDecrypter(encrypted_value)
        depseudo.depseudo_key = privkey_depseudo.decode("utf-8")
        with pytest.raises(DecrypterError, match=r"No analyst key"):
            depseudo.decrypt()

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
        encrypted_value = encrypt_gcm_mode(
            plaintext=plaintext,
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )

        depseudo = DualPKCS1HybridGCMDecrypter(encrypted_value)
        depseudo.depseudo_key = privkey_depseudo.decode("utf-8")
        depseudo.analyst_key = privkey_analyst.decode("utf-8")
        assert depseudo.decrypt() == plaintext


class TestDualPKCS1HybridCTRDecrypter:
    def test_depseudonymize_manual(self, analyst_keys, depseudo_keys):
        privkey_analyst, pubkey_analyst = analyst_keys
        privkey_depseudo, pubkey_depseudo = depseudo_keys
        cipher_rsa_analyst = PKCS1_OAEP.new(RSA.import_key(privkey_analyst.decode("utf-8")))
        cipher_rsa_depseudo = PKCS1_OAEP.new(RSA.import_key(privkey_depseudo.decode("utf-8")))
        encrypted_value = encrypt_ctr_mode(
            plaintext="1",
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )
        assert encrypted_value != "1"
        pseudonym = CTRPseudonym(*[base64.b64decode(value) for value in encrypted_value.split(":")])
        encrypted_session_key = pseudonym.encrypted_session_key
        cipher_nonce = pseudonym.cipher_nonce
        ciphertext = pseudonym.ciphertext
        encrypted_session_key = cipher_rsa_depseudo.decrypt(encrypted_session_key)
        decrypted_session_key = cipher_rsa_analyst.decrypt(encrypted_session_key)
        cipher_aes = AES.new(decrypted_session_key, AES.MODE_CTR, nonce=cipher_nonce)
        decrypted_value = cipher_aes.decrypt(ciphertext).decode("utf-8")
        assert decrypted_value == "1"

    def test_depseudonymizer_depseudonymize_raises_if_no_depseudo_key(
        self, analyst_keys, depseudo_keys
    ):
        _, pubkey_analyst = analyst_keys
        _, pubkey_depseudo = depseudo_keys
        encrypted_value = encrypt_ctr_mode(
            plaintext="1",
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )

        depseudo = DualPKCS1HybridCTRDecrypter(encrypted_value)
        with pytest.raises(DecrypterError, match=r"No depseudo key"):
            depseudo.decrypt()

    def test_depseudonymizer_depseudonymize_raises_if_no_analyst_key(
        self, analyst_keys, depseudo_keys
    ):
        _, pubkey_analyst = analyst_keys
        privkey_depseudo, pubkey_depseudo = depseudo_keys
        encrypted_value = encrypt_ctr_mode(
            plaintext="1",
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )

        depseudo = DualPKCS1HybridCTRDecrypter(encrypted_value)
        depseudo.depseudo_key = privkey_depseudo.decode("utf-8")
        with pytest.raises(DecrypterError, match=r"No analyst key"):
            depseudo.decrypt()

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
        encrypted_value = encrypt_ctr_mode(
            plaintext=plaintext,
            pubkey_analyst=pubkey_analyst,
            pubkey_depseudo=pubkey_depseudo,
        )

        depseudo = DualPKCS1HybridCTRDecrypter(encrypted_value)
        depseudo.depseudo_key = privkey_depseudo.decode("utf-8")
        depseudo.analyst_key = privkey_analyst.decode("utf-8")
        assert depseudo.decrypt() == plaintext
