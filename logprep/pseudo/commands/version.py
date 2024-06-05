import click

from .. import __version__


@click.command()
def print_version():
    """
    Print version string
    """
    print(__version__)
