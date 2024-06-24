# pylint: disable=missing-docstring
from logprep.util.pseudo.keygenerator.generate_rsa_key import generate_keys


class TestRsaKeyGenerator:
    def test_generate_keys_returns_tuple(self):
        pv_key_string, pb_key_string = generate_keys(key_length=1024)
        assert pv_key_string
        assert pb_key_string

    def test_generate_keys_returns_bytes(self):
        pv_key_string, pb_key_string = generate_keys(key_length=1024)
        assert isinstance(pv_key_string, bytes)
        assert isinstance(pb_key_string, bytes)

    def test_generate_tubles_returns_public_and_private_keys(self):
        pv_key_string, pb_key_string = generate_keys(key_length=1024)
        assert "BEGIN PUBLIC KEY" in pb_key_string.decode("utf-8")
        assert "BEGIN RSA PRIVATE KEY" in pv_key_string.decode("utf-8")
