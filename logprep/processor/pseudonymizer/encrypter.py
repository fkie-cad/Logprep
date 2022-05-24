"""Module for encryption of strings into Base64-encoded ciphertexts."""

import base64
from abc import ABC, abstractmethod

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes


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
        with open(keyfile_analyst, "r", encoding="utf8") as file:
            self._pubkey_analyst = RSA.import_key(file.read())
        with open(keyfile_depseudo, "r", encoding="utf8") as file:
            self._pubkey_depseudo = RSA.import_key(file.read())

    def encrypt(
        self,
        input_str: str,
    ) -> str:
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

        output_bytes = enc_session_key + cipher_aes.nonce + ciphertext
        return base64.b64encode(output_bytes).decode("ascii")
