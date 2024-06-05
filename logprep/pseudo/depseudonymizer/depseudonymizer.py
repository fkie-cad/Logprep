"""module to depseudonymize"""

import base64
from dataclasses import dataclass
from Crypto.PublicKey import RSA
from Crypto.Cipher.PKCS1_OAEP import PKCS1OAEP_Cipher
from Crypto.Cipher import AES, PKCS1_OAEP


class DepseudonymizeError(Exception):
    """Depseudonymizer custom Exception"""


@dataclass
class Depseudonymizer:
    """class to depseudonymize a pseudonymized string

    Parameters
    ----------

    pseudonymized_string: str
        The base64 encoded pseudonymized string.
        Base64 decoding is done in __post_init__ method
    """

    pseudonymized_string: str
    """the pseudonymized string"""

    _analyst_key: PKCS1OAEP_Cipher = None

    _depseudo_key: PKCS1OAEP_Cipher = None

    def __post_init__(self) -> None:
        self.pseudonymized_string = base64.b64decode(self.pseudonymized_string)

    @property
    def encrypted_session_key(self) -> bytes:
        """the encrypted session key

        Returns
        -------
        bytes
            the first 16 bytes of the pseudonymized_string
        """
        return self.pseudonymized_string[:256]

    @property
    def cipher_nonce(self) -> bytes:
        """the cipher nonce

        Returns
        -------
        bytes
            The 2 bytes after the session key
        """
        return self.pseudonymized_string[256:264]

    @property
    def ciphertext(self) -> bytes:
        """the cipher text

        Returns
        -------
        bytes
            All bytes after the first 18 bytes
        """
        return self.pseudonymized_string[264:]

    @property
    def depseudo_key(self) -> PKCS1OAEP_Cipher:
        """getter for depseudo_key

        Returns
        -------
        PKCS1OAEP_Cipher
            returns a PKCS1OAEP_Cipher representation of the depseudo key
        """
        return self._depseudo_key

    @depseudo_key.setter
    def depseudo_key(self, depseudo_key: str) -> None:
        """setter for the depseudo_key
        saves the depseudo_key as PKCS1OAEP_Cipher in _depseudo_key

        Parameters
        ----------
        depseudo_key : str
            the depseudo privat key
        """
        self._depseudo_key = RSA.import_key(depseudo_key)

    @property
    def analyst_key(self) -> PKCS1OAEP_Cipher:
        """getter for analyst_key

        Returns
        -------
        PKCS1OAEP_Cipher
            returns a PKCS1OAEP_Cipher representation of the analyst key
        """
        return self._analyst_key

    @analyst_key.setter
    def analyst_key(self, analyst_key: str) -> None:
        """setter for the analyst_key
        saves the analyst_key as PKCS1OAEP_Cipher in _analyst_key

        Parameters
        ----------
        analyst_key : str
            the analyst privat key
        """
        self._analyst_key = RSA.import_key(analyst_key)

    def depseudonymize(self) -> str:
        """depseudonymizes after setting the depseudo and analyst keys

        Returns
        -------
        str
            the depseudonymized string

        Raises
        ------
        DepseudonymizeError
            if depseudo_key or analyst_key is not set
        """
        if self._depseudo_key is None:
            raise DepseudonymizeError("No depseudo key")
        if self._analyst_key is None:
            raise DepseudonymizeError("No analyst key")
        cipher_rsa_depseudo = PKCS1_OAEP.new(self._depseudo_key)
        cipher_rsa_analyst = PKCS1_OAEP.new(self._analyst_key)
        depseudo_decrypted_session_key = cipher_rsa_depseudo.decrypt(self.encrypted_session_key)
        analyst_decrypted_session_key = cipher_rsa_analyst.decrypt(depseudo_decrypted_session_key)
        cipher_aes = AES.new(analyst_decrypted_session_key, AES.MODE_CTR, nonce=self.cipher_nonce)
        return cipher_aes.decrypt(self.ciphertext).decode("utf-8")
