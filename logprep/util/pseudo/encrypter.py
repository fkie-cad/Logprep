"""Module for encryption of strings into Base64-encoded ciphertexts."""

import base64
from abc import ABC, abstractmethod

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

from logprep.util.defaults import DEFAULT_AES_KEY_LENGTH
from logprep.util.getter import GetterFactory
from logprep.util.pseudo.decrypter import CTRPseudonym, GCMPseudonym


class Encrypter(ABC):
    """Base class to encrypt strings into Base64-encoded ciphertexts."""

    def __init__(self):
        self._pubkey_analyst = None
        self._pubkey_depseudo = None

    @abstractmethod
    def encrypt(self, input_str: str) -> str:
        """Encrypt a string into a Base64-encoded ciphertext."""

    def load_public_keys(self, keyfile_analyst: str, keyfile_depseudo: str):
        """Load the two required RSA public keys from files.

        Raises
        ------
        FileNotFoundError
            If a key file cannot be found.
        ValueError
            If a key file does not contain a valid key
        """
        pub_key_analyst_str = GetterFactory.from_string(keyfile_analyst).get()
        self._pubkey_analyst = RSA.import_key(pub_key_analyst_str)
        pub_key_depseudo_str = GetterFactory.from_string(keyfile_depseudo).get()
        self._pubkey_depseudo = RSA.import_key(pub_key_depseudo_str)


class DualPKCS1HybridGCMEncrypter(Encrypter):
    """Hybrid encryption that encrypts a string with AES in GCM Mode and dual PKCS#1"""

    def encrypt(self, input_str: str) -> str:
        """Encrypt a string using hybrid encryption.

        The input string is encrypted with AES in GCM mode using a random
        session key. The session key is then encrypted with a depseudo AES key
        in GCM mode. The depseudo key is then encrypted with the public key
        of the analyst and the encrypted session key is encrypted with the
        public key of the depseudonymizer personnel. This decouples the analyst
        key length from the depseudo key length.

        This leads to additional 152 bytes of overhead for the encryption
        compared to the ctr mode encrypter.

        Returns
        -------
        str
            String representation of the Base64-encoded concatenation of the
            double-encrypted session key, the depseudo key AES nonce, the encrypted
            depseudo key, the AES nonce of the session key and the AES ciphertext
        """
        if not self._pubkey_analyst or not self._pubkey_depseudo:
            raise ValueError("Cannot encrypt because public keys are not loaded")

        # encrypt input string with AES session key
        session_key: bytes = get_random_bytes(DEFAULT_AES_KEY_LENGTH)
        aes_key_input_str = AES.new(session_key, AES.MODE_GCM)
        input_str_enc: bytes = aes_key_input_str.encrypt(input_str.encode("utf-8"))

        # encrypt session key with AES depseudo key
        depseudo_key: bytes = get_random_bytes(DEFAULT_AES_KEY_LENGTH)
        aes_key_depseudo = AES.new(depseudo_key, AES.MODE_GCM)
        session_key_enc: bytes = aes_key_depseudo.encrypt(session_key)

        # encrypt AES depseudo key with depseudo public key
        cipher_rsa_analyst = PKCS1_OAEP.new(self._pubkey_depseudo)
        depseudo_key_enc: bytes = cipher_rsa_analyst.encrypt(depseudo_key)

        # encrypt encrypted session key with analyst public key
        cipher_rsa_depseudo = PKCS1_OAEP.new(self._pubkey_analyst)
        session_key_enc_enc: bytes = cipher_rsa_depseudo.encrypt(session_key_enc)

        # concatenate, encode, and return
        return str(
            GCMPseudonym(
                session_key_enc_enc,
                aes_key_depseudo.nonce,
                depseudo_key_enc,
                aes_key_input_str.nonce,
                input_str_enc,
            )
        )


class DualPKCS1HybridCTREncrypter(Encrypter):
    """Hybrid encryption that encrypts a string with AES in CTR mode and dual PKCS#1"""

    def encrypt(self, input_str: str) -> str:
        """Encrypt a string using hybrid encryption.

        The input string is encrypted with AES in CTR mode using a random
        session key. The session key is then encrypted using PKCS#1 OAEP (RSA)
        with the public keys of the analyst and the de-pseudonymizer. This
        required the latter RSA key to be lager than the former.

        Returns
        -------
        str
            String representation of the Base64-encoded concatenation of the
            double-encrypted session key, the AES nonce, and the AES ciphertext
        """
        if not self._pubkey_analyst or not self._pubkey_depseudo:
            raise ValueError("Cannot encrypt because public keys are not loaded")

        session_key = get_random_bytes(16)

        cipher_rsa_analyst = PKCS1_OAEP.new(self._pubkey_analyst)
        enc_session_key = cipher_rsa_analyst.encrypt(session_key)

        cipher_rsa_depseudo = PKCS1_OAEP.new(self._pubkey_depseudo)
        enc_session_key = cipher_rsa_depseudo.encrypt(enc_session_key)

        cipher_aes = AES.new(session_key, AES.MODE_CTR)
        ciphertext = cipher_aes.encrypt(input_str.encode("utf-8"))

        return str(CTRPseudonym(enc_session_key, cipher_aes.nonce, ciphertext))
