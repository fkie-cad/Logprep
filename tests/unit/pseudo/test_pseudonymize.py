from Crypto.PublicKey import RSA

from logprep.processor.pseudonymizer.encrypter import DualPKCS1HybridEncrypter
from logprep.pseudo.keygenerator.generate_rsa_key import generate_keys


class TestPseudonymizer:
    def test_pseudonymize(self):
        public_key_analyst, private_key_analyst = generate_keys(
            key_length=1024,
        )
        public_key_depseudo, private_key_depseudo = generate_keys(key_length=2048)
        encrypter = DualPKCS1HybridEncrypter()
        encrypter._pubkey_analyst = RSA.import_key(public_key_analyst.decode("utf-8"))
        encrypter._pubkey_depseudo = RSA.import_key(public_key_depseudo.decode("utf-8"))
        value = "1"
        encrypted_origin = encrypter.encrypt(value)
        assert value != encrypted_origin
