"""Pseudonymize a string using the given keys and method."""

import click

from logprep.util.pseudo.encrypter import (
    DualPKCS1HybridCTREncrypter,
    DualPKCS1HybridGCMEncrypter,
)


@click.command()
@click.argument("analyst-key", type=click.Path(exists=True))
@click.argument("depseudo-key", type=click.Path(exists=True))
@click.argument("string", type=str)
@click.option(
    "--mode",
    type=click.Choice(["gcm", "ctr"]),
    default="ctr",
    help="The mode to use for decryption",
)
def pseudonymize(analyst_key: str, depseudo_key: str, string: str, mode: str):
    """pseudonymize a string using the given keys."""
    encrypter = DualPKCS1HybridGCMEncrypter() if mode == "gcm" else DualPKCS1HybridCTREncrypter()
    encrypter.load_public_keys(
        keyfile_analyst=f"{analyst_key}",
        keyfile_depseudo=f"{depseudo_key}",
    )
    print(encrypter.encrypt(string))
