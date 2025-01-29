# Copyright Jonathan Hartley 2013. BSD 3-Clause license, see LICENSE file.
"""
This module generates ANSI character codes to printing colors to terminals.
See: http://en.wikipedia.org/wiki/ANSI_escape_code
This module contains only a subset of the original colorama library. Additional codes can be added in this module from
https://github.com/tartley/colorama/blob/master/colorama/ansi.py.
"""

CSI = "\033["
OSC = "\033]"
BEL = "\a"


def code_to_chars(code):
    return CSI + str(code) + "m"


class AnsiCodes(object):
    def __init__(self):
        # the subclasses declare class attributes which are numbers.
        # Upon instantiation we define instance attributes, which are the same
        # as the class attributes but wrapped with the ANSI escape sequence
        for name in dir(self):
            if not name.startswith("_"):
                value = getattr(self, name)
                setattr(self, name, code_to_chars(value))


class AnsiFore(AnsiCodes):
    BLACK = 30
    RED = 31
    GREEN = 32
    YELLOW = 33
    BLUE = 34
    MAGENTA = 35
    CYAN = 36
    WHITE = 37
    RESET = 39


class AnsiBack(AnsiCodes):
    RESET = 49


Fore = AnsiFore()
Back = AnsiBack()
