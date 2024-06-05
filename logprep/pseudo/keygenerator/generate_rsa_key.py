from Crypto.PublicKey import RSA


def generate_keys(key_length):
    key = RSA.generate(key_length)
    pv_key_string = key.exportKey()
    pb_key_string = key.publickey().exportKey()
    return pv_key_string, pb_key_string
