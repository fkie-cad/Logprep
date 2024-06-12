"""module to depseudonymize"""

import base64
from abc import abstractmethod
from dataclasses import dataclass

from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Cipher.PKCS1_OAEP import PKCS1OAEP_Cipher
from Crypto.PublicKey import RSA


class DecrypterError(Exception):
    """Depseudonymizer custom Exception"""


@dataclass
class CTRPseudonym:
    """CTR pseudonym representation"""

    encrypted_session_key: bytes
    """encrypted session key"""
    cipher_nonce: bytes
    """cipher nonce"""
    ciphertext: bytes
    """ciphertext"""

    def __str__(self):
        return (
            f"{base64.b64encode(self.encrypted_session_key).decode('ascii')}:"
            f"{base64.b64encode(self.cipher_nonce).decode('ascii')}:"
            f"{base64.b64encode(self.ciphertext).decode('ascii')}"
        )


@dataclass
class GCMPseudonym:
    """GCM pseudonym representation"""

    session_key_enc_enc: bytes
    """double encrypted session key"""
    aes_key_depseudo_nonce: bytes
    """AES depseudo key nonce"""
    depseudo_key_enc: bytes
    """encrypted depseudo key"""
    aes_key_input_str_nonce: bytes
    """AES input string nonce"""
    ciphertext: bytes
    """ciphertext"""

    def __str__(self):
        return (
            f"{base64.b64encode(self.session_key_enc_enc).decode('ascii')}:"
            f"{base64.b64encode(self.aes_key_depseudo_nonce).decode('ascii')}:"
            f"{base64.b64encode(self.depseudo_key_enc).decode('ascii')}:"
            f"{base64.b64encode(self.aes_key_input_str_nonce).decode('ascii')}:"
            f"{base64.b64encode(self.ciphertext).decode('ascii')}"
        )


@dataclass
class Decrypter:
    """class to depseudonymize a pseudonymized string

    Parameters
    ----------

    pseudonym: CTRPseudonym | GCMPseudonym
        The base64 encoded pseudonymized string.
        Conversion to CTRPseudonym or GCMPseudonym is done in __post_init__ method
    """

    pseudonym: CTRPseudonym | GCMPseudonym | str
    """the pseudonymized string"""

    _analyst_key: PKCS1OAEP_Cipher = None

    _depseudo_key: PKCS1OAEP_Cipher = None

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
            the depseudo private key
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
            the analyst private key
        """
        self._analyst_key = RSA.import_key(analyst_key)

    @abstractmethod
    def decrypt(self) -> str:
        """abstract method to decrypt the pseudonym"""


@dataclass
class DualPKCS1HybridCTRDecrypter(Decrypter):
    """class to depseudonymize a pseudonymized string

    Parameters
    ----------

    pseudonym: CTRPseudonym | GCMPseudonym
        The base64 encoded pseudonymized string.
        Conversion to CTRPseudonym is done in __post_init__ method
    """

    def __post_init__(self) -> None:
        self.pseudonym = CTRPseudonym(
            *[base64.b64decode(value) for value in self.pseudonym.split(":")]
        )

    def decrypt(self) -> str:
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
            raise DecrypterError("No depseudo key")
        if self._analyst_key is None:
            raise DecrypterError("No analyst key")
        cipher_rsa_depseudo = PKCS1_OAEP.new(self._depseudo_key)
        cipher_rsa_analyst = PKCS1_OAEP.new(self._analyst_key)
        depseudo_decrypted_session_key = cipher_rsa_depseudo.decrypt(
            self.pseudonym.encrypted_session_key
        )
        analyst_decrypted_session_key = cipher_rsa_analyst.decrypt(depseudo_decrypted_session_key)
        cipher_aes = AES.new(
            analyst_decrypted_session_key,
            AES.MODE_CTR,
            nonce=self.pseudonym.cipher_nonce,
        )
        return cipher_aes.decrypt(self.pseudonym.ciphertext).decode("utf-8")


@dataclass
class DualPKCS1HybridGCMDecrypter(Decrypter):
    """class to depseudonymize a pseudonymized string

    Parameters
    ----------

    pseudonym: CTRPseudonym | GCMPseudonym
        The base64 encoded pseudonymized string.
        Conversion to GCMPseudonym is done in __post_init__ method
    """

    def __post_init__(self) -> None:
        self.pseudonym = GCMPseudonym(
            *[base64.b64decode(value) for value in self.pseudonym.split(":")]
        )

    def decrypt(self) -> str:
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
            raise DecrypterError("No depseudo key")
        if self._analyst_key is None:
            raise DecrypterError("No analyst key")
        cipher_rsa_depseudo = PKCS1_OAEP.new(self._depseudo_key)
        cipher_rsa_analyst = PKCS1_OAEP.new(self._analyst_key)
        # decrypt double encrypted session key with analyst private key
        session_key_enc: bytes = cipher_rsa_analyst.decrypt(self.pseudonym.session_key_enc_enc)

        # decrypt AES depseudo key with depseudo private key
        depseudo_key: bytes = cipher_rsa_depseudo.decrypt(self.pseudonym.depseudo_key_enc)

        # decrypt session key with AES depseudo key
        aes_key = AES.new(depseudo_key, AES.MODE_GCM, self.pseudonym.aes_key_depseudo_nonce)
        session_key: bytes = aes_key.decrypt(session_key_enc)

        # decrypt ciphertext with AES session key
        aes_key_input_str = AES.new(
            session_key, AES.MODE_GCM, self.pseudonym.aes_key_input_str_nonce
        )
        return aes_key_input_str.decrypt(self.pseudonym.ciphertext).decode("utf-8")
