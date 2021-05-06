"""This module contains helper functions that are shared by different modules."""

from typing import Optional

from colorama import Fore, Back
from colorama.ansi import AnsiFore, AnsiBack


def print_color(back: Optional[AnsiBack], fore: Optional[AnsiFore], message: str):
    """Print string with colors and reset the color afterwards."""
    color = ''
    if back:
        color += back
    if fore:
        color += fore

    print(color + message + Fore.RESET + Back.RESET)


def print_bcolor(back: AnsiBack, message: str):
    """Print string with background color and reset the color afterwards."""
    print_color(back, None, message)


def print_fcolor(fore: AnsiFore, message: str):
    """Print string with colored font and reset the color afterwards."""
    print_color(None, fore, message)
