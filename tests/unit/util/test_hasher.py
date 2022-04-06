from logprep.util.hasher import SHA256Hasher


class TestSHA256Hasher:
    def test_hash_str_without_salt(self):
        assert (
            SHA256Hasher().hash_str("foo")
            == "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae"
        )

    def test_hash_str_with_salt(self):
        assert (
            SHA256Hasher().hash_str("foo", salt="bar")
            == "c3ab8ff13720e8ad9047dd39466b3c8974e592c2fa383d4a3960714caef0c4f2"
        )
