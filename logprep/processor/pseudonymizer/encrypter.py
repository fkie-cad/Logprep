"""Module for encryption of strings into Base64-encoded ciphertexts."""

import base64
from abc import ABC, abstractmethod

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes

from logprep.util.getter import GetterFactory


class Encrypter(ABC):
    """Base class to encrypt strings into Base64-encoded ciphertexts."""

    @abstractmethod
    def encrypt(self, input_str: str) -> str:
        """Encrypt a string into a Base64-encoded ciphertext."""


class DualPKCS1HybridEncrypter(Encrypter):
    """Hybrid encryption that encrypts a string with AES and dual PKCS#1"""

    def __init__(self):
        self._pubkey_analyst = None
        self._pubkey_depseudo = None

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

    def encrypt(self, input_str: str) -> str:
        """Encrypt a string using hybrid encryption.

        The input string is encrypted with AES in GCM mode using a random
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

        # encrypt input string with AES session key
        session_key = get_random_bytes(16)
        aes_key_input_str = AES.new(session_key, AES.MODE_GCM)

        input_str_enc = aes_key_input_str.encrypt(input_str.encode("utf-8"))

        # encrpyt session key with depseudo key
        depseudo_key = get_random_bytes(16)
        aes_key_depseudo = AES.new(depseudo_key, AES.MODE_GCM)
        session_key_enc = aes_key_depseudo.encrypt(session_key)

        # encrypt aes_key_depseudo with depseudo public key

        cipher_rsa_analyst = PKCS1_OAEP.new(self._pubkey_analyst)
        depseudo_key_enc = cipher_rsa_analyst.encrypt(depseudo_key)

        cipher_rsa_depseudo = PKCS1_OAEP.new(self._pubkey_depseudo)
        session_key_enc_enc = cipher_rsa_depseudo.encrypt(session_key_enc)
        output = (
            f'{base64.b64encode(session_key_enc_enc).decode("ascii")}||'
            f'{base64.b64encode(depseudo_key_enc).decode("ascii")}||'
            f'{base64.b64encode(input_str_enc).decode("ascii")}'
        )
        return output
