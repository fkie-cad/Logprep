"""Command line tool to depseudonymize a string using the given keys."""

import logging
import sys

import click

from logprep.util.pseudo.decrypter import (
    DualPKCS1HybridCTRDecrypter,
    DualPKCS1HybridGCMDecrypter,
)


@click.command()
@click.argument("analyst-key", type=click.Path(exists=True))
@click.argument("depseudo-key", type=click.Path(exists=True))
@click.argument("pseudo-string", type=str)
@click.option(
    "--mode",
    type=click.Choice(["gcm", "ctr"]),
    default="ctr",
    help="The mode to use for decryption",
)
def depseudonymize(analyst_key: str, depseudo_key: str, pseudo_string: str, mode: str):
    """depseudonymize a string using the given keys."""
    depseudo = (
        DualPKCS1HybridGCMDecrypter(pseudo_string)
        if mode == "gcm"
        else DualPKCS1HybridCTRDecrypter(pseudo_string)
    )
    keys = {}
    for key_file_name in analyst_key, depseudo_key:
        with open(f"{key_file_name}", "r", encoding="utf8") as key_file:
            keys[key_file_name] = key_file.read()
    depseudo.depseudo_key = keys[depseudo_key]
    depseudo.analyst_key = keys[analyst_key]
    try:
        print(depseudo.decrypt())
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
