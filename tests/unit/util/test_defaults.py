import unittest

from logprep.util.defaults import EXITCODES


class TestEXITCODES(unittest.TestCase):

    def test_to_bytes(self):
        exit_code = EXITCODES.SUCCESS
        expected_bytes = b"\x00"
        result = exit_code.to_bytes(1, byteorder="big")
        self.assertEqual(result, expected_bytes)

        exit_code = EXITCODES.ERROR
        expected_bytes = b"\x01"
        result = exit_code.to_bytes(1, byteorder="little")
        self.assertEqual(result, expected_bytes)

    def test_from_bytes(self):
        bytes_obj = b"\x00"
        result = EXITCODES.from_bytes(bytes_obj, byteorder="big")
        self.assertEqual(result, EXITCODES.SUCCESS)

        bytes_obj = b"\x01"
        result = EXITCODES.from_bytes(bytes_obj, byteorder="little")
        self.assertEqual(result, EXITCODES.ERROR)


if __name__ == "__main__":
    unittest.main()
