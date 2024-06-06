import click

from logprep.util.pseudo.keygenerator import generate_rsa_key


@click.command()
@click.argument("key-length", default="1024", type=int)
@click.option("-f", "--file")
def generate(key_length: int, file: str):
    """Generate RSA keys for pseudonymization."""
    priv_key, pub_key = generate_rsa_key.generate_keys(key_length=key_length)
    if not file:
        print(priv_key.decode("utf8"))
        print(pub_key.decode("utf8"))
    else:
        with open(f"{file}.key", "w", encoding="utf8") as private_key_file:
            private_key_file.write(priv_key.decode("utf8"))
        with open(f"{file}.crt", "w", encoding="utf8") as public_key_file:
            public_key_file.write(pub_key.decode("utf8"))
