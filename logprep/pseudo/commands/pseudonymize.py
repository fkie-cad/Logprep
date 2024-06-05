import click
from logprep.processor.pseudonymizer.encrypter import DualPKCS1HybridEncrypter


@click.command()
@click.argument("analyst-key", type=str)
@click.argument("depseudo-key", type=str)
@click.argument("string", type=str)
def pseudonymize(analyst_key: str, depseudo_key: str, string: str):
    encrypter = DualPKCS1HybridEncrypter()
    encrypter.load_public_keys(
        keyfile_analyst=f"{analyst_key}.crt",
        keyfile_depseudo=f"{depseudo_key}.crt",
    )
    print(encrypter.encrypt(string))
