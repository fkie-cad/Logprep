"""Pseudonymize a string using the given keys and method."""

import click

from logprep.util.pseudo.commands.encrypter import DualPKCS1HybridCTREncrypter


@click.command()
@click.argument("analyst-key", type=str)
@click.argument("depseudo-key", type=str)
@click.argument("string", type=str)
def pseudonymize(analyst_key: str, depseudo_key: str, string: str):
    """pseudonymize a string using the given keys."""
    encrypter = DualPKCS1HybridCTREncrypter()
    encrypter.load_public_keys(
        keyfile_analyst=f"{analyst_key}.crt",
        keyfile_depseudo=f"{depseudo_key}.crt",
    )
    print(encrypter.encrypt(string))
