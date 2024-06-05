import click

from ..depseudonymizer.depseudonymizer import Depseudonymizer


@click.command()
@click.argument("analyst-key", type=str)
@click.argument("depseudo-key", type=str)
@click.argument("pseudo-string", type=str)
def depseudonymize(analyst_key: str, depseudo_key: str, pseudo_string: str):
    depseudo = Depseudonymizer(pseudo_string)
    keys = {}
    for key_file_name in analyst_key, depseudo_key:
        with open(f"{key_file_name}.key", "r", encoding="utf8") as key_file:
            keys[key_file_name] = key_file.read()
    depseudo.depseudo_key = keys[depseudo_key]
    depseudo.analyst_key = keys[analyst_key]
    print(depseudo.depseudonymize())
